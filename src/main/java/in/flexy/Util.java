package in.flexy;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Pattern;

/** Helpers + validation (port of middleware/validation.py, rate_limiter.py). */
public final class Util {
    private Util() {}
    static final Pattern EMAIL = Pattern.compile("^[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}$");
    static final Pattern USERNAME = Pattern.compile("^[a-zA-Z0-9_]{3,30}$");

    public static Map<String, Object> m(Object... kv) {
        Map<String, Object> r = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) r.put((String) kv[i], kv[i + 1]);
        return r;
    }
    public static String s(Object o) { return o == null ? "" : String.valueOf(o); }
    public static boolean truthy(Object o) {
        if (o == null) return false;
        if (o instanceof Boolean b) return b;
        if (o instanceof Number n) return n.doubleValue() != 0;
        return !o.toString().isEmpty();
    }
    public static long lng(Object o) {
        if (o == null) return 0;
        if (o instanceof Number n) return n.longValue();
        try { return (long) Double.parseDouble(o.toString()); } catch (Exception e) { return 0; }
    }
    public static double dbl(Object o) {
        if (o == null) return 0;
        if (o instanceof Number n) return n.doubleValue();
        try { return Double.parseDouble(o.toString()); } catch (Exception e) { return 0; }
    }
    public static OffsetDateTime nowDt() { return OffsetDateTime.now(ZoneOffset.UTC); }
    public static String now() { return nowDt().toString(); }
    public static OffsetDateTime parse(Object o) {
        if (o == null || s(o).isBlank()) return null;
        String t = s(o).trim().replace(' ', 'T');
        try { return OffsetDateTime.parse(t); }
        catch (Exception e) { return LocalDateTime.parse(t).atOffset(ZoneOffset.UTC); }
    }
    public static String ip(HttpServletRequest r) {
        String x = r.getHeader("X-Forwarded-For");
        if (x != null && !x.isBlank()) return x.split(",")[0].trim();
        return r.getRemoteAddr() == null ? "127.0.0.1" : r.getRemoteAddr();
    }
    public static String ua(HttpServletRequest r) {
        String u = r.getHeader("User-Agent");
        return u == null ? "" : u.substring(0, Math.min(500, u.length()));
    }
    public static Map<String, Object> body(Map<String, Object> b) { return b == null ? new HashMap<>() : b; }

    // ── validation (throws IllegalArgumentException → HTTP 422) ──
    public static String email(Object o) {
        if (!(o instanceof String e)) throw new IllegalArgumentException("Email must be a string");
        e = e.trim().toLowerCase();
        if (!EMAIL.matcher(e).matches()) throw new IllegalArgumentException("Invalid email address");
        return e;
    }
    public static String password(Object o) {
        if (!(o instanceof String p)) throw new IllegalArgumentException("Password must be a string");
        if (p.length() < 8) throw new IllegalArgumentException("Password must be at least 8 characters");
        if (p.length() > 128) throw new IllegalArgumentException("Password too long");
        if (!Pattern.compile("[A-Z]").matcher(p).find()) throw new IllegalArgumentException("Password must contain at least one uppercase letter");
        if (!Pattern.compile("[a-z]").matcher(p).find()) throw new IllegalArgumentException("Password must contain at least one lowercase letter");
        if (!Pattern.compile("\\d").matcher(p).find()) throw new IllegalArgumentException("Password must contain at least one digit");
        return p;
    }
    public static String username(Object o) {
        if (!(o instanceof String u)) throw new IllegalArgumentException("Username must be a string");
        u = u.trim();
        if (!USERNAME.matcher(u).matches()) throw new IllegalArgumentException("Username must be 3–30 alphanumeric characters or underscores");
        return u;
    }
    public static long bid(Object o) {
        long v;
        try { v = (long) (o instanceof Number n ? n.doubleValue() : Double.parseDouble(String.valueOf(o))); }
        catch (Exception e) { throw new IllegalArgumentException("Invalid bid amount"); }
        if (v <= 0) throw new IllegalArgumentException("Bid amount must be positive");
        if (v > 10_000_000_000L) throw new IllegalArgumentException("Bid amount exceeds maximum allowed");
        return v;
    }
    public static String sanitise(Object o, int max) {
        if (!(o instanceof String s)) throw new IllegalArgumentException("Expected a string");
        s = s.trim();
        if (s.length() > max) throw new IllegalArgumentException("Text exceeds " + max + " characters");
        return s.replaceAll("(?is)<script.*?>.*?</script>", "");
    }

    // ── simple in-memory sliding-window rate limiter ──
    private static final Map<String, Deque<Long>> HITS = new ConcurrentHashMap<>();
    public static void rate(String key, int max, long windowSec) {
        long now = System.currentTimeMillis(), from = now - windowSec * 1000;
        Deque<Long> q = HITS.computeIfAbsent(key, k -> new ArrayDeque<>());
        synchronized (q) {
            while (!q.isEmpty() && q.peekFirst() < from) q.pollFirst();
            if (q.size() >= max) throw new ApiException(429, "Too many requests. Please try again later.");
            q.addLast(now);
        }
    }
}

class ApiException extends RuntimeException {
    final int status; final Map<String, Object> body;
    ApiException(int status, String msg) { super(msg); this.status = status; this.body = Util.m("error", msg); }
    ApiException(int status, Map<String, Object> body) { super(Util.s(body.get("error"))); this.status = status; this.body = body; }
}

@RestControllerAdvice
class Errors {
    @ExceptionHandler(ApiException.class)
    ResponseEntity<Object> api(ApiException e) { return ResponseEntity.status(e.status).body(e.body); }
    @ExceptionHandler(IllegalArgumentException.class)
    ResponseEntity<Object> bad(IllegalArgumentException e) { return ResponseEntity.status(422).body(Util.m("error", e.getMessage())); }
    @ExceptionHandler(Exception.class)
    ResponseEntity<Object> other(Exception e) {
        if (e instanceof org.springframework.web.ErrorResponse er)
            return ResponseEntity.status(er.getStatusCode()).body(Util.m("error", "Request error"));
        if (e instanceof org.springframework.http.converter.HttpMessageNotReadableException)
            return ResponseEntity.status(400).body(Util.m("error", "Invalid JSON body"));
        e.printStackTrace();
        return ResponseEntity.status(500).body(Util.m("error", "Internal server error"));
    }
}
