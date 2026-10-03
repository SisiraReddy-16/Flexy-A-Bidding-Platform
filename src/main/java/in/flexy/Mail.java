package in.flexy;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;

/** Email via Brevo HTTP API (port of email_service.py). Same env vars: BREVO_API_KEY, MAIL_USERNAME, MAIL_FROM_NAME. */
@Component
public class Mail {
    private final String apiKey, sender, name;
    private final HttpClient http = HttpClient.newHttpClient();
    private final ObjectMapper om = new ObjectMapper();

    public Mail(Environment e) {
        apiKey = e.getProperty("BREVO_API_KEY", ""); sender = e.getProperty("MAIL_USERNAME", ""); name = e.getProperty("MAIL_FROM_NAME", "Flexy");
    }

    private void send(String to, String subject, String html, String plain) {
        System.out.printf("%n%s%n  FLEXY MAIL  ->  %s%n  Subject: %s%n  %s%n%s%n%n", "=".repeat(62), to, subject, plain, "=".repeat(62));
        if (apiKey.isEmpty() || sender.isEmpty()) { System.out.println("[MAIL ERROR] BREVO_API_KEY or MAIL_USERNAME env var is not set!"); return; }
        new Thread(() -> {
            try {
                String body = om.writeValueAsString(Map.of("sender", Map.of("name", name, "email", sender),
                    "to", List.of(Map.of("email", to)), "subject", subject, "htmlContent", html));
                var req = HttpRequest.newBuilder(URI.create("https://api.brevo.com/v3/smtp/email")).timeout(Duration.ofSeconds(20))
                    .header("api-key", apiKey).header("Content-Type", "application/json").header("Accept", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body)).build();
                var r = http.send(req, HttpResponse.BodyHandlers.ofString());
                System.out.println(r.statusCode() < 300 ? "[MAIL SUCCESS] Brevo accepted -> " + r.body() : "[MAIL ERROR] Brevo HTTP " + r.statusCode() + ": " + r.body());
            } catch (Exception e) { System.out.println("[MAIL ERROR] " + e); }
        }).start();
    }

    public void sendVerification(String to, String username, String otp) {
        String html = """
            <!DOCTYPE html><html><head><meta charset="utf-8"/></head>
            <body style="margin:0;padding:0;background:#0e0e0e;font-family:'Segoe UI',Arial,sans-serif;">
            <table width="100%%" cellpadding="0" cellspacing="0" style="background:#0e0e0e;padding:2rem 0;"><tr><td align="center">
            <table width="520" cellpadding="0" cellspacing="0" style="background:#141414;border:1px solid #2a2a2a;border-radius:16px;overflow:hidden;max-width:520px;">
              <tr><td style="background:linear-gradient(135deg,#44007f,#9c3dff);padding:2rem;text-align:center;">
                <h1 style="margin:0;font-size:2.25rem;font-weight:900;color:#fff;">Flexy</h1>
                <p style="margin:.25rem 0 0;color:rgba(255,255,255,.7);font-size:.85rem;">High-Velocity Bidding Platform</p></td></tr>
              <tr><td style="padding:2.5rem 2rem;">
                <h2 style="color:#fff;margin:0 0 .5rem;font-size:1.4rem;">Welcome, %s! 👋</h2>
                <p style="color:#999;margin:0 0 2rem;line-height:1.7;font-size:.95rem;">Use this OTP to verify your account. It expires in <strong style="color:#ff94a3;">10 minutes</strong>.</p>
                <div style="text-align:center;margin:0 0 2rem;"><div style="display:inline-block;background:#1a0035;border:2px solid #c899ff;border-radius:14px;padding:1.25rem 3rem;">
                  <span style="font-size:2.75rem;font-weight:900;letter-spacing:.4em;color:#c899ff;font-family:'Courier New',monospace;">%s</span></div>
                  <p style="color:#666;font-size:.8rem;margin:.75rem 0 0;">Never share this OTP with anyone.</p></div></td></tr>
              <tr><td style="background:#0a0a0a;padding:1rem 2rem;text-align:center;border-top:1px solid #1e1e1e;">
                <p style="color:#444;font-size:.75rem;margin:0;">© 2026 Flexy · India's Premium Bidding Platform</p></td></tr>
            </table></td></tr></table></body></html>""".formatted(username, otp);
        send(to, "Flexy OTP: " + otp, html, "Your OTP is: " + otp + " (expires in 10 minutes)");
    }
    // Placeholders – same as the Python version
    public void sendPasswordReset(String to, String username, String token) { System.out.println("[MAIL] Password reset email placeholder for " + to); }
    public void sendLoginAlert(String to, String username, String ip, String ua) { System.out.println("[MAIL] Login alert placeholder for " + to); }
    public void sendAuctionWon(String to, String username, String title, long amount, String orderId) { System.out.println("[MAIL] Auction won email placeholder for " + to); }
}
