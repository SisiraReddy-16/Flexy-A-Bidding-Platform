package in.flexy;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.config.annotation.*;

import java.nio.charset.StandardCharsets;
import java.util.*;

import static in.flexy.Util.m;

/** Serves frontend pages + static files, health and admin-seed endpoints (port of the page routes in app.py). */
@RestController
public class WebController {
    private final Environment env; private final Seeder seeder;
    public WebController(Environment env, Seeder seeder) { this.env = env; this.seeder = seeder; }

    private ResponseEntity<String> page(String name, HttpServletRequest r) throws Exception {
        String html = new String(new ClassPathResource("frontend/templates/" + name + ".html").getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        String sock = env.getProperty("SOCKET_URL", "");
        if (sock.isEmpty()) sock = r.getScheme() + "://" + r.getServerName() + ":" + env.getProperty("SOCKET_PORT", "9092");
        html = html.replace("__SOCKET_URL__", sock);
        return ResponseEntity.ok().contentType(MediaType.TEXT_HTML).body(html);
    }

    @GetMapping({"/", "/login"}) ResponseEntity<String> login(HttpServletRequest r) throws Exception { return page("login", r); }
    @GetMapping("/signup") ResponseEntity<String> signup(HttpServletRequest r) throws Exception { return page("signup", r); }
    @GetMapping("/dashboard") ResponseEntity<String> dashboard(HttpServletRequest r) throws Exception { return page("dashboard", r); }
    @GetMapping({"/auction", "/auction/{id}"}) ResponseEntity<String> auction(HttpServletRequest r) throws Exception { return page("auction", r); }
    @GetMapping("/create") ResponseEntity<String> create(HttpServletRequest r) throws Exception { return page("create", r); }
    @GetMapping("/wallet") ResponseEntity<String> wallet(HttpServletRequest r) throws Exception { return page("wallet", r); }
    @GetMapping("/settings") ResponseEntity<String> settings(HttpServletRequest r) throws Exception { return page("settings", r); }
    @GetMapping("/notifications") ResponseEntity<String> notifications(HttpServletRequest r) throws Exception { return page("notifications", r); }
    @GetMapping("/watchlist") ResponseEntity<String> watchlist(HttpServletRequest r) throws Exception { return page("watchlist", r); }
    @GetMapping("/verify-email") ResponseEntity<String> verifyEmail(HttpServletRequest r) throws Exception { return page("verify_email", r); }
    @GetMapping("/reset-password") ResponseEntity<String> resetPw(HttpServletRequest r) throws Exception { return page("reset_password", r); }
    @GetMapping("/order/{id}") ResponseEntity<String> order(HttpServletRequest r) throws Exception { return page("order", r); }
    @GetMapping("/my-orders") ResponseEntity<String> myOrders(HttpServletRequest r) throws Exception { return page("my_orders", r); }

    @GetMapping("/health") Object health() { return m("status", "ok", "service", "flexy-backend"); }

    @PostMapping("/api/admin/seed")
    ResponseEntity<Object> adminSeed(@RequestHeader(value = "X-Seed-Secret", required = false) String hdr) {
        String secret = env.getProperty("SEED_SECRET", "");
        if (secret.isEmpty()) return ResponseEntity.status(503).body(m("error", "SEED_SECRET env var not configured"));
        if (!secret.equals(hdr)) return ResponseEntity.status(401).body(m("error", "Unauthorized"));
        try { seeder.seed(); return ResponseEntity.ok(m("status", "ok", "message", "Seed completed successfully")); }
        catch (Exception e) { return ResponseEntity.status(500).body(m("status", "error", "message", e.getMessage())); }
    }
}

@Configuration
class WebConfig implements WebMvcConfigurer {
    private final Environment env;
    WebConfig(Environment env) { this.env = env; }

    @Override public void addResourceHandlers(ResourceHandlerRegistry reg) {
        reg.addResourceHandler("/static/**").addResourceLocations("classpath:/frontend/static/")
           .setCacheControl(org.springframework.http.CacheControl.maxAge(java.time.Duration.ofDays(7)).cachePublic());
    }
    @Override public void addCorsMappings(CorsRegistry reg) {
        reg.addMapping("/api/**").allowedOrigins(env.getProperty("FRONTEND_URL", "http://localhost:5000"), "http://127.0.0.1:5000", "http://localhost:5000")
           .allowCredentials(true).allowedMethods("*").allowedHeaders("*");
    }
    @Override public void addInterceptors(InterceptorRegistry reg) {
        reg.addInterceptor(new org.springframework.web.servlet.HandlerInterceptor() {
            @Override public boolean preHandle(jakarta.servlet.http.HttpServletRequest q, jakarta.servlet.http.HttpServletResponse p, Object h) {
                if (q.getRequestURI().startsWith("/api/")) p.setHeader("Cache-Control", "no-store"); return true;
            }
        });
    }
}
