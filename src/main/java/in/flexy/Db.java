package in.flexy;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.*;

/** Lightweight Supabase PostgREST client (port of database.py). Same Supabase project/tables. */
@Component
public class Db {
    private final String url, key;
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();
    private final ObjectMapper om = new ObjectMapper();

    public Db(Environment env) {
        this.url = env.getProperty("SUPABASE_URL", "").replaceAll("/+$", "");
        this.key = env.getProperty("SUPABASE_KEY", "");
    }

    @PostConstruct
    void ping() {
        if (url.isEmpty() || key.isEmpty()) { System.out.println("[DB] Warning: SUPABASE_URL or SUPABASE_KEY not set."); return; }
        try {
            var r = http.send(HttpRequest.newBuilder(URI.create(url + "/rest/v1/")).header("apikey", key)
                    .header("Authorization", "Bearer " + key).timeout(Duration.ofSeconds(10)).GET().build(),
                    HttpResponse.BodyHandlers.discarding());
            System.out.println(r.statusCode() < 500 ? "[DB] Connected to Supabase successfully." : "[DB] Warning: Supabase returned " + r.statusCode());
        } catch (Exception e) { System.out.println("[DB] Warning: Could not reach Supabase at startup: " + e.getMessage()); }
    }

    public Q table(String name) {
        if (url.isEmpty() || key.isEmpty()) throw new IllegalStateException("Database not initialised. Check SUPABASE_URL and SUPABASE_KEY");
        return new Q(name);
    }

    public record Res(List<Map<String, Object>> data, Long count) {
        public Map<String, Object> first() { return data.isEmpty() ? null : data.get(0); }
    }

    private static String enc(Object v) { return URLEncoder.encode(String.valueOf(v), StandardCharsets.UTF_8).replace("+", "%20"); }

    public class Q {
        private final String table;
        private final List<String> filters = new ArrayList<>();
        private String select = "*", order, op = "select";
        private Integer limit, offset;
        private boolean count;
        private Object data;

        Q(String t) { this.table = t; }
        public Q select(String cols) { select = cols; return this; }
        public Q selectCount(String cols) { select = cols; count = true; return this; }
        public Q eq(String c, Object v) { filters.add(c + "=eq." + enc(v)); return this; }
        public Q neq(String c, Object v) { filters.add(c + "=neq." + enc(v)); return this; }
        public Q lt(String c, Object v) { filters.add(c + "=lt." + enc(v)); return this; }
        public Q gt(String c, Object v) { filters.add(c + "=gt." + enc(v)); return this; }
        public Q ilike(String c, String p) { filters.add(c + "=ilike." + enc(p)); return this; }
        public Q order(String c, boolean desc) { order = c + (desc ? ".desc" : ".asc"); return this; }
        public Q limit(int n) { limit = n; return this; }
        public Q range(int start, int end) { offset = start; limit = end - start + 1; return this; }
        public Q insert(Object d) { op = "insert"; data = d; return this; }
        public Q update(Object d) { op = "update"; data = d; return this; }
        public Q delete() { op = "delete"; return this; }

        public Res execute() {
            StringBuilder qs = new StringBuilder("select=" + select);
            for (String f : filters) qs.append('&').append(f);
            if (order != null) qs.append("&order=").append(order);
            if (limit != null) qs.append("&limit=").append(limit);
            if (offset != null) qs.append("&offset=").append(offset);
            try {
                var b = HttpRequest.newBuilder(URI.create(url + "/rest/v1/" + table + "?" + qs)).timeout(Duration.ofSeconds(15))
                        .header("apikey", key).header("Authorization", "Bearer " + key).header("Content-Type", "application/json");
                String json = data == null ? "" : om.writeValueAsString(data);
                switch (op) {
                    case "insert" -> b.header("Prefer", "return=representation").POST(HttpRequest.BodyPublishers.ofString(json));
                    case "update" -> b.header("Prefer", "return=representation").method("PATCH", HttpRequest.BodyPublishers.ofString(json));
                    case "delete" -> b.header("Prefer", "return=representation").DELETE();
                    default -> { if (count) b.header("Prefer", "count=exact"); b.GET(); }
                }
                HttpResponse<String> r = http.send(b.build(), HttpResponse.BodyHandlers.ofString());
                if (r.statusCode() >= 400) throw new RuntimeException("Supabase " + r.statusCode() + ": " + r.body().substring(0, Math.min(300, r.body().length())));
                List<Map<String, Object>> rows = new ArrayList<>();
                String body = r.body();
                if (body != null && !body.isBlank()) {
                    Object parsed = om.readValue(body, new TypeReference<Object>() {});
                    if (parsed instanceof List<?> l) for (Object o : l) { @SuppressWarnings("unchecked") var mm = (Map<String, Object>) o; rows.add(mm); }
                    else if (parsed instanceof Map<?, ?> mp) { @SuppressWarnings("unchecked") var mm = (Map<String, Object>) mp; rows.add(mm); }
                }
                Long cnt = null;
                if (count) {
                    String cr = r.headers().firstValue("Content-Range").orElse("");
                    int i = cr.indexOf('/');
                    try { cnt = i >= 0 ? Long.parseLong(cr.substring(i + 1)) : (long) rows.size(); } catch (Exception e) { cnt = (long) rows.size(); }
                }
                return new Res(rows, cnt);
            } catch (RuntimeException e) { throw e; }
            catch (Exception e) { throw new RuntimeException(e); }
        }
    }
}
