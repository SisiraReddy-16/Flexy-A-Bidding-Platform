package in.flexy;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.core.env.Environment;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

import java.time.Duration;
import java.time.OffsetDateTime;
import java.security.SecureRandom;
import java.util.*;

import static in.flexy.Util.*;

@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private static final String DUMMY_HASH = "$2b$12$wXvhavbM/xMS6WBYV6Et7.pZXoNHjM5XYbr3Erjmjig1qOAw2dMVy";
    private final Store st; private final Auth auth; private final Mail mail; private final boolean prod;

    public AuthController(Store st, Auth auth, Mail mail, Environment env) {
        this.st = st; this.auth = auth; this.mail = mail; this.prod = "production".equals(env.getProperty("FLASK_ENV"));
    }

    private ResponseEntity<Object> withCookie(int status, Object body, String token, long maxAge) {
        ResponseCookie c = ResponseCookie.from(Auth.COOKIE, token).httpOnly(true).secure(prod).sameSite("Lax")
            .path("/").maxAge(Duration.ofSeconds(maxAge)).build();
        return ResponseEntity.status(status).header(HttpHeaders.SET_COOKIE, c.toString()).body(body);
    }
    private static ResponseEntity<Object> r(int s, Object b) { return ResponseEntity.status(s).body(b); }

    @PostMapping("/signup")
    public ResponseEntity<Object> signup(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest req) {
        Util.rate("signup:" + ip(req), 10, 3600);
        var d = body(body);
        String email = email(d.getOrDefault("email", "")), username = username(d.getOrDefault("username", "")), pw = password(d.getOrDefault("password", ""));
        if (st.userByEmail(email) != null) return r(200, m("message", "If that email is available, a verification OTP has been sent."));
        if (st.userByUsername(username) != null) return r(409, m("error", "Username already taken"));
        var user = st.createUser(email, username, pw);
        try { mail.sendVerification(email, username, s(user.get("email_verification_token"))); } catch (Exception e) { System.out.println("[MAIL] " + e); }
        st.log("signup", s(user.get("id")), ip(req));
        return r(201, m("message", "Account created. Please check your email for the OTP to verify your account."));
    }

    @PostMapping("/resend-verification")
    public ResponseEntity<Object> resend(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest req) {
        Util.rate("resend:" + ip(req), 3, 3600);
        var ok = r(200, m("message", "If that email exists, a new OTP has been sent."));
        String email;
        try { email = email(body(body).getOrDefault("email", "")); } catch (IllegalArgumentException e) { return ok; }
        var user = st.userByEmail(email);
        if (user != null && !Boolean.TRUE.equals(user.get("is_email_verified"))) {
            String token = st.otp();
            st.setVerificationToken(s(user.get("id")), token);
            try { mail.sendVerification(email, s(user.get("username")), token); } catch (Exception ignored) {}
        }
        return ok;
    }

    @PostMapping("/verify-otp")
    public ResponseEntity<Object> verifyOtp(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest req) {
        Util.rate("otp:" + ip(req), 10, 900);
        var d = body(body);
        String email = s(d.get("email")).trim().toLowerCase(), otp = s(d.get("otp")).trim();
        if (email.isEmpty() || otp.isEmpty()) return r(400, m("error", "Email and OTP are required"));
        var user = st.userByEmail(email);
        if (user == null) return r(404, m("error", "User not found"));
        if (Boolean.TRUE.equals(user.get("is_email_verified"))) return r(200, m("message", "Email is already verified."));
        if (!otp.equals(user.get("email_verification_token"))) return r(400, m("error", "Invalid OTP."));
        OffsetDateTime exp = parse(user.get("email_verification_expires"));
        if (exp != null && nowDt().isAfter(exp))
            return r(400, m("error", "OTP has expired. Please request a new one.", "expired", true, "email", email));
        String uid = s(user.get("id"));
        st.markEmailVerified(uid);
        st.log("email_verified", uid, ip(req));
        st.resetFailedLogin(uid); st.updateLastLogin(uid);
        String token = st.createSession(uid, ip(req), ua(req));
        try { mail.sendLoginAlert(s(user.get("email")), s(user.get("username")), ip(req), ua(req)); } catch (Exception ignored) {}
        Map<String, Object> u = new HashMap<>(user); u.put("is_email_verified", true);
        return withCookie(200, m("user", st.safeUser(u), "message", "Email verified and logged in successfully."), token, 86400);
    }

    @GetMapping("/verify-email")
    public ResponseEntity<Object> verifyEmailLink(@RequestParam(defaultValue = "") String token, HttpServletRequest req) {
        token = token.trim();
        if (token.isEmpty()) return r(400, m("error", "No token provided."));
        var user = st.userByVerifyToken(token);
        if (user == null) return r(400, m("error", "This verification link is invalid or has already been used."));
        if (Boolean.TRUE.equals(user.get("is_email_verified"))) return r(200, m("message", "Email is already verified."));
        OffsetDateTime exp = parse(user.get("email_verification_expires"));
        if (exp != null && nowDt().isAfter(exp))
            return r(400, m("error", "This verification link has expired. Please request a new one.", "expired", true, "email", user.get("email")));
        String uid = s(user.get("id"));
        st.markEmailVerified(uid); st.log("email_verified", uid, ip(req));
        st.resetFailedLogin(uid); st.updateLastLogin(uid);
        return r(200, m("message", "Your email has been verified! You can now log in."));
    }

    @PostMapping("/login")
    public ResponseEntity<Object> login(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest req) {
        Util.rate("login:" + ip(req), 5, 900);
        var d = body(body); String ip = ip(req);
        String email, password;
        try {
            email = email(d.getOrDefault("email", ""));
            if (!(d.get("password") instanceof String p) || p.isEmpty()) throw new IllegalArgumentException("Password required");
            password = p;
        } catch (IllegalArgumentException e) { return r(401, m("error", "Invalid credentials")); }

        var user = st.userByEmail(email);
        boolean ok = st.verifyPassword(password, user != null ? s(user.get("password_hash")) : DUMMY_HASH);
        if (!ok || user == null) {
            if (user != null) { st.incrementFailedLogin(email); st.log("login_failed", s(user.get("id")), ip, m("reason", "bad_password")); }
            return r(401, m("error", "Invalid credentials"));
        }
        String uid = s(user.get("id"));
        if (Boolean.TRUE.equals(user.get("is_locked"))) {
            OffsetDateTime until = parse(user.get("locked_until"));
            if (until != null && nowDt().isBefore(until)) {
                long mins = Duration.between(nowDt(), until).toSeconds() / 60;
                return r(403, m("error", "Account locked. Try again in " + mins + " minutes."));
            }
            st.resetFailedLogin(uid);
        }
        if (!Boolean.TRUE.equals(user.get("is_email_verified")))
            return r(403, m("error", "Please verify your email before logging in.", "unverified", true, "email", email));

        if (Boolean.TRUE.equals(user.get("mfa_enabled")) && truthy(user.get("mfa_secret"))) {
            String otp = s(d.get("otp"));
            if (otp.isEmpty()) return r(200, m("mfa_required", true));
            if (!Mfa.verify(s(user.get("mfa_secret")), otp)) {
                st.log("mfa_failed", uid, ip);
                return r(401, m("error", "Invalid OTP code. Check your authenticator app."));
            }
        }
        st.resetFailedLogin(uid); st.updateLastLogin(uid);
        String token = st.createSession(uid, ip, ua(req));
        st.log("login_success", uid, ip);
        try { mail.sendLoginAlert(s(user.get("email")), s(user.get("username")), ip, ua(req)); } catch (Exception ignored) {}
        return withCookie(200, m("user", st.safeUser(user), "message", "Login successful"), token, 86400);
    }

    @PostMapping("/logout")
    public ResponseEntity<Object> logout(HttpServletRequest req) {
        var u = auth.user(req);
        st.invalidateSession(auth.token(req));
        st.log("logout", s(u.get("id")), ip(req));
        return withCookie(200, m("message", "Logged out"), "", 0);
    }

    @PostMapping("/forgot-password")
    public ResponseEntity<Object> forgot(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest req) {
        Util.rate("forgot:" + ip(req), 5, 3600);
        var ok = r(200, m("message", "If that email is registered, a reset link has been sent."));
        String email;
        try { email = email(body(body).getOrDefault("email", "")); } catch (IllegalArgumentException e) { return ok; }
        var user = st.userByEmail(email);
        if (user != null) {
            try {
                byte[] b = new byte[32]; new SecureRandom().nextBytes(b);
                String token = Base64.getUrlEncoder().withoutPadding().encodeToString(b);
                st.setResetToken(s(user.get("id")), token);
                mail.sendPasswordReset(email, s(user.get("username")), token);
                st.log("password_reset_requested", s(user.get("id")), ip(req));
            } catch (Exception ignored) {}
        }
        return ok;
    }

    @PostMapping("/reset-password")
    public ResponseEntity<Object> reset(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest req) {
        var d = body(body); String token = s(d.get("token")).trim();
        if (token.isEmpty()) return r(400, m("error", "Reset token is required"));
        String pw = password(d.getOrDefault("password", ""));
        var user = st.userByResetToken(token);
        if (user == null) return r(400, m("error", "Invalid or expired reset link."));
        OffsetDateTime exp = parse(user.get("password_reset_expires"));
        if (exp != null && nowDt().isAfter(exp)) return r(400, m("error", "Reset link has expired. Please request a new one."));
        String uid = s(user.get("id"));
        st.updatePassword(uid, pw); st.invalidateAllSessions(uid);
        st.log("password_reset_completed", uid, ip(req));
        return r(200, m("message", "Password updated. All sessions have been logged out."));
    }

    @PostMapping("/change-password")
    public ResponseEntity<Object> change(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest req) {
        var user = auth.user(req); var d = body(body);
        String cur = s(d.get("current_password"));
        if (cur.isEmpty()) return r(422, m("error", "Current password required"));
        if (!st.verifyPassword(cur, s(user.get("password_hash")))) return r(401, m("error", "Current password is incorrect"));
        String np = password(d.getOrDefault("new_password", ""));
        String uid = s(user.get("id"));
        st.updatePassword(uid, np);
        String current = auth.token(req);
        for (var s : st.userSessions(uid)) if (!current.equals(s.get("token"))) st.db.table("sessions").update(m("is_valid", false)).eq("id", s(s.get("id"))).execute();
        st.log("password_changed", uid, ip(req));
        return r(200, m("message", "Password changed successfully. Other sessions logged out."));
    }

    @PostMapping("/mfa/setup")
    public ResponseEntity<Object> mfaSetup(HttpServletRequest req) {
        var user = auth.user(req);
        String secret = Mfa.generateSecret();
        return r(200, m("secret", secret, "qr_code", Mfa.qrBase64(Mfa.uri(secret, s(user.get("username"))))));
    }

    @PostMapping("/mfa/verify")
    public ResponseEntity<Object> mfaVerify(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest req) {
        var user = auth.user(req); var d = body(body);
        String secret = s(d.get("secret")).trim(), code = s(d.get("code")).trim();
        if (secret.isEmpty() || code.isEmpty()) return r(422, m("error", "Secret and code are required"));
        if (!Mfa.verify(secret, code)) return r(401, m("error", "Invalid OTP code."));
        st.setMfaSecret(s(user.get("id")), secret);
        st.log("mfa_enabled", s(user.get("id")), ip(req));
        return r(200, m("message", "Two-factor authentication enabled successfully."));
    }

    @PostMapping("/mfa/disable")
    public ResponseEntity<Object> mfaDisable(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest req) {
        var user = auth.user(req); String code = s(body(body).get("code")).trim();
        if (!Boolean.TRUE.equals(user.get("mfa_enabled"))) return r(400, m("error", "MFA is not enabled on this account"));
        if (code.isEmpty()) return r(422, m("error", "OTP code required to disable MFA"));
        if (!Mfa.verify(s(user.get("mfa_secret")), code)) return r(401, m("error", "Invalid OTP code"));
        st.disableMfa(s(user.get("id")));
        st.log("mfa_disabled", s(user.get("id")), ip(req));
        return r(200, m("message", "Two-factor authentication has been disabled."));
    }

    @GetMapping("/sessions")
    public ResponseEntity<Object> sessions(HttpServletRequest req) {
        var user = auth.user(req); String cur = auth.token(req);
        List<Object> out = new ArrayList<>();
        for (var s : st.userSessions(s(user.get("id")))) {
            String ua = s(s.get("user_agent"));
            out.add(m("id", s(s.get("id")), "ip", s.get("ip") == null ? "—" : s.get("ip"), "user_agent", ua.substring(0, Math.min(80, ua.length())),
                "created_at", s.get("created_at"), "current", cur.equals(s.get("token"))));
        }
        return r(200, m("sessions", out));
    }

    @DeleteMapping("/sessions/{sid}")
    public ResponseEntity<Object> revoke(@PathVariable String sid, HttpServletRequest req) {
        var user = auth.user(req);
        var found = st.db.table("sessions").select("*").eq("id", sid).eq("user_id", s(user.get("id"))).execute();
        if (found.data().isEmpty()) return r(404, m("error", "Session not found"));
        st.db.table("sessions").update(m("is_valid", false)).eq("id", sid).execute();
        st.log("session_revoked", s(user.get("id")), ip(req), m("session_id", sid));
        return r(200, m("message", "Session revoked"));
    }

    @GetMapping("/me")
    public ResponseEntity<Object> me(HttpServletRequest req) { return r(200, m("user", st.safeUser(auth.user(req)))); }
}
