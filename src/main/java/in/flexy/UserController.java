package in.flexy;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.*;
import java.util.regex.Pattern;

import static in.flexy.Util.*;

@RestController
@RequestMapping("/api/user")
public class UserController {
    private final Store st; private final Auth auth;
    public UserController(Store st, Auth auth) { this.st = st; this.auth = auth; }

    @GetMapping("/profile")
    public Object profile(HttpServletRequest r) { return m("user", st.safeUser(auth.user(r))); }

    @PutMapping("/profile")
    public ResponseEntity<Object> update(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest r) {
        var u = auth.user(r); var d = body(body); Map<String, Object> upd = new HashMap<>();
        Object[][] fields = {{"bio", 300}, {"avatar_url", 500}, {"location", 100}};
        for (var f : fields) if (d.containsKey(f[0])) upd.put((String) f[0], sanitise(d.get(f[0]), (Integer) f[1]));
        if (upd.isEmpty()) return ResponseEntity.status(422).body(m("error", "Nothing to update"));
        st.updateUser(s(u.get("id")), upd);
        return ResponseEntity.ok(m("message", "Profile updated", "user", st.safeUser(st.userById(s(u.get("id"))))));
    }

    @GetMapping("/stats")
    public Object stats(HttpServletRequest r) {
        var u = auth.user(r); String uid = s(u.get("id"));
        var won = st.db.table("auctions").select("id,current_bid").eq("status", "ended").eq("current_bidder", uid).execute().data();
        Set<String> ids = new HashSet<>();
        for (var b : st.db.table("bids").select("auction_id").eq("bidder_id", uid).execute().data()) ids.add(s(b.get("auction_id")));
        int active = 0;
        for (String aid : ids) if (!st.db.table("auctions").select("id").eq("id", aid).eq("status", "active").execute().data().isEmpty()) active++;
        long wonVal = 0; for (var a : won) wonVal += lng(a.get("current_bid"));
        return m("items_won", won.size(), "active_bids", active, "total_valuation_inr", (lng(u.get("wallet_balance")) + wonVal) / 100.0);
    }

    @GetMapping("/audit-log")
    public Object audit(HttpServletRequest r) {
        List<Object> out = new ArrayList<>();
        for (var e : st.recentEvents(s(auth.user(r).get("id"))))
            out.add(m("event_type", e.get("event_type"), "ip", e.getOrDefault("ip", ""), "meta", e.getOrDefault("meta", new HashMap<>()), "created_at", e.get("created_at")));
        return m("events", out);
    }

    @GetMapping("/my-auctions")
    public Object myAuctions(@RequestParam(defaultValue = "20") int limit, @RequestParam(defaultValue = "0") int skip, HttpServletRequest r) {
        var u = auth.user(r); limit = Math.min(limit, 50);
        List<Object> out = new ArrayList<>();
        for (var a : st.db.table("auctions").select("*").eq("created_by", s(u.get("id"))).order("created_at", true).range(skip, skip + limit - 1).execute().data()) out.add(st.safeAuction(a));
        return m("auctions", out);
    }

    @GetMapping("/my-bids")
    public Object myBids(@RequestParam(defaultValue = "20") int limit, @RequestParam(defaultValue = "0") int skip, HttpServletRequest r) {
        var u = auth.user(r); limit = Math.min(limit, 50);
        List<Object> out = new ArrayList<>();
        for (var b : st.db.table("bids").select("*").eq("bidder_id", s(u.get("id"))).order("created_at", true).range(skip, skip + limit - 1).execute().data()) {
            var a = st.db.table("auctions").select("id,title").eq("id", s(b.get("auction_id"))).execute().first();
            out.add(m("id", s(b.get("id")), "amount", b.get("amount"), "amount_inr", lng(b.get("amount")) / 100.0, "auction_id", s(b.get("auction_id")),
                "auction_title", a != null ? a.get("title") : "Unknown", "created_at", b.get("created_at")));
        }
        return m("bids", out);
    }

    @PostMapping("/kyc")
    public ResponseEntity<Object> kyc(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest r) {
        var u = auth.user(r); var d = body(body);
        String name = s(d.get("legal_name")).trim(), pan = s(d.get("pan")).trim().toUpperCase(), aad = s(d.get("aadhaar_last4")).trim(),
               bank = s(d.get("bank_account")).trim(), ifsc = s(d.get("bank_ifsc")).trim().toUpperCase();
        if (name.isEmpty()) return ResponseEntity.status(422).body(m("error", "Legal name is required"));
        if (!Pattern.matches("^[A-Z]{5}[0-9]{4}[A-Z]$", pan)) return ResponseEntity.status(422).body(m("error", "Invalid PAN format (e.g. ABCDE1234F)"));
        if (!Pattern.matches("^[0-9]{4}$", aad)) return ResponseEntity.status(422).body(m("error", "Enter last 4 digits of Aadhaar"));
        st.updateUser(s(u.get("id")), m("kyc_status", "approved", "is_seller_verified", true, "kyc_legal_name", name, "kyc_pan", pan,
            "kyc_aadhaar_last4", aad, "kyc_bank_account", bank, "kyc_bank_ifsc", ifsc, "kyc_submitted_at", now()));
        return ResponseEntity.ok(m("message", "KYC approved. You can now list items for auction."));
    }

    @GetMapping("/kyc")
    public Object kycStatus(HttpServletRequest r) {
        var u = auth.user(r);
        return m("kyc_status", u.getOrDefault("kyc_status", "not_submitted"), "is_seller_verified", u.getOrDefault("is_seller_verified", false));
    }
}
