package in.flexy;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.stereotype.Component;

import java.util.Map;

/** Cookie/Bearer session auth (port of middleware/auth_middleware.py). */
@Component
public class Auth {
    public static final String COOKIE = "flexy_session";
    private final Store st;
    public Auth(Store st) { this.st = st; }

    public String token(HttpServletRequest r) {
        if (r.getCookies() != null)
            for (Cookie c : r.getCookies()) if (COOKIE.equals(c.getName()) && !c.getValue().isEmpty()) return c.getValue();
        String h = r.getHeader("Authorization");
        return h != null && h.startsWith("Bearer ") ? h.substring(7) : null;
    }
    /** Like @jwt_required. */
    public Map<String, Object> user(HttpServletRequest r) {
        String t = token(r);
        if (t == null) throw new ApiException(401, "Authentication required");
        var s = st.getSession(t);
        if (s == null) throw new ApiException(401, "Session expired or invalid");
        var u = st.userById(Util.s(s.get("user_id")));
        if (u == null) throw new ApiException(401, "User not found");
        if (Boolean.TRUE.equals(u.get("is_locked"))) throw new ApiException(403, "Account is locked. Contact support.");
        return u;
    }
    /** Like @jwt_required + @email_verified_required. */
    public Map<String, Object> verified(HttpServletRequest r) {
        var u = user(r);
        if (!Boolean.TRUE.equals(u.get("is_email_verified"))) throw new ApiException(403, "Email verification required");
        return u;
    }
}
