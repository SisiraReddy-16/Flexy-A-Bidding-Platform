package in.flexy;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.core.env.Environment;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.net.URI;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.*;

import static in.flexy.Util.*;

@RestController
@RequestMapping("/api/wallet")
public class WalletController {
    static final long MAX_DEPOSIT = 10_000_000_00L, MAX_WITHDRAW = 1_000_000_00L;
    private final Store st; private final Auth auth; private final Environment env;
    private final HttpClient http = HttpClient.newHttpClient();
    private final com.fasterxml.jackson.databind.ObjectMapper om = new com.fasterxml.jackson.databind.ObjectMapper();

    public WalletController(Store st, Auth auth, Environment env) { this.st = st; this.auth = auth; this.env = env; }

    private void tx(String uid, String type, long amt, String note, String rzpId) {
        var row = m("id", Store.id(), "user_id", uid, "type", type, "amount", amt, "note", note, "created_at", now());
        if (rzpId != null) row.put("razorpay_payment_id", rzpId);
        st.db.table("transactions").insert(row).execute();
    }
    private long setBalance(Map<String, Object> user, long delta) {
        long nb = lng(user.get("wallet_balance")) + delta;
        st.db.table("users").update(m("wallet_balance", nb, "updated_at", now())).eq("id", s(user.get("id"))).execute();
        return nb;
    }
    private Map<String, Object> bal(String msg, long nb) { return m("message", msg, "balance_paise", nb, "balance_inr", nb / 100.0); }
    private String clean(String k) { return env.getProperty(k, "").trim().replaceAll("^[\"']|[\"']$", ""); }

    @GetMapping("/balance")
    public Object balance(HttpServletRequest r) {
        long b = lng(auth.user(r).get("wallet_balance")); return m("balance_paise", b, "balance_inr", b / 100.0);
    }

    @PostMapping("/deposit")
    public ResponseEntity<Object> deposit(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest r) {
        var u = auth.verified(r); long amt = bid(body(body).getOrDefault("amount", 0));
        if (amt > MAX_DEPOSIT) return ResponseEntity.status(422).body(m("error", "Deposit exceeds maximum limit"));
        long nb = setBalance(u, amt); tx(s(u.get("id")), "deposit", amt, "Manual deposit", null);
        st.log("wallet_deposit", s(u.get("id")), ip(r), m("amount", amt));
        return ResponseEntity.ok(bal("Deposit successful", nb));
    }

    @PostMapping("/withdraw")
    public ResponseEntity<Object> withdraw(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest r) {
        var u = auth.verified(r); long amt = bid(body(body).getOrDefault("amount", 0));
        if (amt > MAX_WITHDRAW) return ResponseEntity.status(422).body(m("error", "Withdrawal exceeds maximum limit"));
        if (lng(u.get("wallet_balance")) < amt) return ResponseEntity.status(402).body(m("error", "Insufficient balance"));
        long nb = setBalance(u, -amt); tx(s(u.get("id")), "withdraw", amt, "Withdrawal request", null);
        st.log("wallet_withdraw", s(u.get("id")), ip(r), m("amount", amt));
        return ResponseEntity.ok(bal("Withdrawal successful", nb));
    }

    @GetMapping("/transactions")
    public Object transactions(@RequestParam(defaultValue = "20") int limit, @RequestParam(defaultValue = "0") int skip, HttpServletRequest r) {
        var u = auth.user(r); limit = Math.min(limit, 100);
        List<Object> out = new ArrayList<>();
        for (var t : st.db.table("transactions").select("*").eq("user_id", s(u.get("id"))).order("created_at", true).range(skip, skip + limit - 1).execute().data())
            out.add(m("id", s(t.get("id")), "type", t.get("type"), "amount", t.get("amount"), "amount_inr", lng(t.get("amount")) / 100.0,
                "note", t.getOrDefault("note", ""), "created_at", t.get("created_at")));
        return m("transactions", out);
    }

    @PostMapping("/razorpay/order")
    public ResponseEntity<Object> rzpOrder(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest r) throws Exception {
        var u = auth.verified(r); long amt = bid(body(body).getOrDefault("amount", 0));
        String key = clean("RAZORPAY_KEY_ID"), secret = clean("RAZORPAY_KEY_SECRET");
        if (key.isEmpty() || secret.isEmpty())
            return ResponseEntity.ok(m("order_id", "order_sandbox_" + UUID.randomUUID().toString().replace("-", "").substring(0, 16),
                "amount", amt, "currency", "INR", "key", "rzp_test_sandbox", "sandbox", true));
        try {
            String receipt = ("flexy_" + s(u.get("id")).replace("-", "").substring(0, 20));
            String payload = om.writeValueAsString(m("amount", amt, "currency", "INR", "receipt", receipt.substring(0, Math.min(40, receipt.length())), "payment_capture", 1));
            String cred = Base64.getEncoder().encodeToString((key + ":" + secret).getBytes(StandardCharsets.UTF_8));
            var resp = http.send(HttpRequest.newBuilder(URI.create("https://api.razorpay.com/v1/orders")).timeout(Duration.ofSeconds(10))
                .header("Content-Type", "application/json").header("Authorization", "Basic " + cred)
                .POST(HttpRequest.BodyPublishers.ofString(payload)).build(), HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() >= 400) {
                System.out.println("[RAZORPAY] HTTPError " + resp.statusCode() + ": " + resp.body());
                return ResponseEntity.status(502).body(m("error", "Razorpay error " + resp.statusCode() + ": " + resp.body()));
            }
            @SuppressWarnings("unchecked") Map<String, Object> o = om.readValue(resp.body(), Map.class);
            return ResponseEntity.ok(m("order_id", o.get("id"), "amount", amt, "currency", "INR", "key", key));
        } catch (Exception e) {
            System.out.println("[RAZORPAY] Unexpected error: " + e);
            return ResponseEntity.status(500).body(m("error", "Payment gateway error: " + e.getMessage()));
        }
    }

    @PostMapping("/razorpay/verify")
    public ResponseEntity<Object> rzpVerify(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest r) throws Exception {
        var u = auth.verified(r); var d = body(body); String uid = s(u.get("id"));
        String oid = s(d.get("razorpay_order_id")), pid = s(d.get("razorpay_payment_id")), sig = s(d.get("razorpay_signature"));
        long amt = lng(d.get("amount")); String secret = clean("RAZORPAY_KEY_SECRET");
        if (secret.isEmpty() || oid.startsWith("order_sandbox_")) {
            if (amt <= 0) return ResponseEntity.status(400).body(m("error", "Invalid amount"));
            long nb = setBalance(u, amt); tx(uid, "deposit", amt, "Razorpay sandbox deposit", null);
            st.log("wallet_deposit", uid, ip(r), m("amount", amt, "mode", "sandbox"));
            return ResponseEntity.ok(bal("Wallet credited successfully", nb));
        }
        Mac mac = Mac.getInstance("HmacSHA256"); mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        StringBuilder hex = new StringBuilder();
        for (byte b : mac.doFinal((oid + "|" + pid).getBytes(StandardCharsets.UTF_8))) hex.append(String.format("%02x", b));
        if (!MessageDigest.isEqual(hex.toString().getBytes(), sig.getBytes())) {
            st.log("payment_tampered", uid, ip(r), m("order_id", oid));
            return ResponseEntity.status(400).body(m("error", "Payment verification failed"));
        }
        if (!st.db.table("transactions").select("id").eq("razorpay_payment_id", pid).execute().data().isEmpty())
            return ResponseEntity.status(400).body(m("error", "Payment already processed"));
        long nb = setBalance(u, amt); tx(uid, "deposit", amt, "Razorpay " + pid, pid);
        st.log("wallet_deposit", uid, ip(r), m("amount", amt, "mode", "razorpay"));
        return ResponseEntity.ok(bal("Wallet credited successfully", nb));
    }
}
