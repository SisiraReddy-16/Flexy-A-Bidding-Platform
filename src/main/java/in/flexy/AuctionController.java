package in.flexy;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.OffsetDateTime;
import java.util.*;

import static in.flexy.Util.*;

@RestController
@RequestMapping("/api/auctions")
public class AuctionController {
    private final Store st; private final Auth auth; private final SocketService socket;
    public AuctionController(Store st, Auth auth, SocketService socket) { this.st = st; this.auth = auth; this.socket = socket; }

    private String autoStatus(Map<String, Object> a) {
        var now = nowDt(); String status = s(a.getOrDefault("status", "active"));
        var ends = parse(a.get("ends_at")); var starts = parse(a.get("starts_at"));
        if (status.equals("ended")) return "ended";
        if (status.equals("upcoming") && starts != null && !now.isBefore(starts)) {
            st.db.table("auctions").update(m("status", "active")).eq("id", s(a.get("id"))).execute(); return "active";
        }
        if (status.equals("active") && ends != null && now.isAfter(ends)) { st.endAuction(s(a.get("id"))); return "ended"; }
        return status;
    }
    private List<Object> safeList(List<Map<String, Object>> l) { List<Object> o = new ArrayList<>(); for (var a : l) o.add(st.safeAuction(a)); return o; }

    @GetMapping({"", "/"})
    public Object list(@RequestParam(defaultValue = "active") String status, @RequestParam(required = false) String category,
                       @RequestParam(defaultValue = "ends_at") String sort, @RequestParam(defaultValue = "20") int limit,
                       @RequestParam(defaultValue = "0") int skip, @RequestParam(name = "q", defaultValue = "") String q) {
        limit = Math.min(limit, 50);
        var qb = st.db.table("auctions").select("*").eq("status", status);
        if (category != null && !category.equals("all")) qb = qb.eq("category", category);
        if (!q.isBlank()) qb = qb.ilike("title", "%" + q.trim() + "%");
        String col; boolean desc;
        switch (sort) { case "bid_high" -> { col = "current_bid"; desc = true; } case "newest" -> { col = "created_at"; desc = true; }
            case "popular" -> { col = "bid_count"; desc = true; } default -> { col = "ends_at"; desc = false; } }
        var rows = qb.order(col, desc).range(skip, skip + limit - 1).execute().data();
        return m("auctions", safeList(rows), "count", rows.size());
    }

    @GetMapping("/sections")
    public Object sections() {
        var db = st.db;
        try {
            var now = nowDt();
            for (var a : db.table("auctions").select("id,ends_at").eq("status", "active").execute().data()) {
                var e = parse(a.get("ends_at")); if (e != null && now.isAfter(e)) st.endAuction(s(a.get("id")));
            }
            for (var a : db.table("auctions").select("id,starts_at").eq("status", "upcoming").execute().data()) {
                var sd = parse(a.get("starts_at")); if (sd != null && !now.isBefore(sd)) db.table("auctions").update(m("status", "active")).eq("id", s(a.get("id"))).execute();
            }
        } catch (Exception ignored) {}
        var feat = db.table("auctions").select("*").eq("status", "active").eq("is_featured", true).order("ends_at", false).limit(6).execute().data();
        return m("live_now", q("active", "ends_at", false, 8), "upcoming", q("upcoming", "ends_at", false, 8),
                 "ended", q("ended", "created_at", true, 4), "popular", q("active", "bid_count", true, 8), "featured", safeList(feat));
    }
    private List<Object> q(String status, String col, boolean desc, int lim) {
        return safeList(st.db.table("auctions").select("*").eq("status", status).order(col, desc).limit(lim).execute().data());
    }

    @GetMapping("/categories")
    public Object categories() {
        Map<String, Integer> cats = new HashMap<>();
        for (var row : st.db.table("auctions").select("category").neq("status", "ended").execute().data()) {
            String c = truthy(row.get("category")) ? s(row.get("category")) : "Other"; cats.merge(c, 1, Integer::sum);
        }
        List<Object> out = new ArrayList<>();
        cats.entrySet().stream().sorted((a, b) -> b.getValue() - a.getValue()).forEach(e -> out.add(m("name", e.getKey(), "count", e.getValue())));
        return m("categories", out);
    }

    @PostMapping({"", "/"})
    public ResponseEntity<Object> create(@RequestBody(required = false) Map<String, Object> body, HttpServletRequest req) {
        var user = auth.verified(req); var d = body(body);
        if (!Boolean.TRUE.equals(user.get("is_seller_verified")))
            return ResponseEntity.status(403).body(m("error", "Seller KYC required. Complete verification in Settings."));
        String title = sanitise(d.getOrDefault("title", ""), 120), desc = sanitise(d.getOrDefault("description", ""), 2000),
               cat = sanitise(d.getOrDefault("category", "Other"), 50), img = sanitise(d.getOrDefault("image_url", ""), 500);
        long sp = bid(d.getOrDefault("starting_price", 0));
        long rp = truthy(d.get("reserve_price")) ? bid(d.get("reserve_price")) : 0;
        int hours;
        try { hours = d.get("duration_hours") == null ? 24 : (int) lng(d.get("duration_hours")); } catch (Exception e) { throw new IllegalArgumentException("Invalid duration"); }
        if (hours < 1 || hours > 168) throw new IllegalArgumentException("Duration must be 1–168 hours");
        if (title.isEmpty()) return ResponseEntity.status(422).body(m("error", "Title is required"));
        var a = st.createAuction(m("title", title, "description", desc, "category", cat, "image_url", img, "starting_price", sp,
            "reserve_price", rp, "ends_at", nowDt().plusHours(hours).toString(), "tags", d.getOrDefault("tags", new ArrayList<>())), s(user.get("id")));
        st.log("auction_created", s(user.get("id")), ip(req), m("auction_id", s(a.get("id"))));
        return ResponseEntity.status(201).body(m("auction", st.safeAuction(a), "message", "Auction created"));
    }

    @GetMapping("/{id}")
    public ResponseEntity<Object> get(@PathVariable String id, HttpServletRequest req) {
        var a = st.getAuction(id);
        if (a == null) return ResponseEntity.status(404).body(m("error", "Auction not found"));
        String real = autoStatus(a); a.put("status", real);
        var ends = parse(a.get("ends_at"));
        var res = st.safeAuction(a);
        res.put("seconds_left", real.equals("active") && ends != null ? Math.max(0, java.time.Duration.between(nowDt(), ends).getSeconds()) : 0);
        var seller = st.userById(s(a.get("created_by")));
        if (seller != null) res.put("seller", m("username", seller.get("username"), "avatar_url", seller.getOrDefault("avatar_url", "")));
        try { st.db.table("auctions").update(m("view_count", lng(a.get("view_count")) + 1)).eq("id", id).execute(); } catch (Exception ignored) {}
        try {
            String token = auth.token(req);
            if (token != null) {
                var sess = st.getSession(token);
                if (sess != null) {
                    String uid = s(sess.get("user_id"));
                    res.put("is_watching", st.isWatching(uid, id));
                    if (real.equals("ended") && uid.equals(s(a.get("current_bidder")))) {
                        var o = st.db.table("orders").select("id,status").eq("auction_id", id).eq("user_id", uid).execute().first();
                        if (o != null) { res.put("order_id", s(o.get("id"))); res.put("order_status", o.get("status")); }
                    }
                }
            }
        } catch (Exception e) { res.put("is_watching", false); }
        return ResponseEntity.ok(m("auction", res));
    }

    @PostMapping("/{id}/bid")
    public ResponseEntity<Object> placeBid(@PathVariable String id, @RequestBody(required = false) Map<String, Object> body, HttpServletRequest req) {
        var user = auth.verified(req); var d = body(body);
        long amt = d.containsKey("amount_inr") ? Math.round(dbl(d.get("amount_inr")) * 100) : bid(d.getOrDefault("amount", 0));
        var a = st.getAuction(id);
        if (a == null) return ResponseEntity.status(404).body(m("error", "Auction not found"));
        String real = autoStatus(a);
        if (!real.equals("active")) return ResponseEntity.status(400).body(m("error", "Auction is " + real + ", not accepting bids"));
        if (s(a.get("created_by")).equals(s(user.get("id")))) return ResponseEntity.status(403).body(m("error", "Cannot bid on your own auction"));
        if (amt <= lng(a.get("current_bid")))
            return ResponseEntity.status(422).body(m("error", "Bid must exceed current bid of ₹" + String.format("%,d", lng(a.get("current_bid")) / 100)));
        if (lng(user.get("wallet_balance")) < amt) return ResponseEntity.status(402).body(m("error", "Insufficient wallet balance"));
        var bid = st.placeBid(id, s(user.get("id")), amt);
        long nb = lng(user.get("wallet_balance")) - amt;
        st.db.table("users").update(m("wallet_balance", nb)).eq("id", s(user.get("id"))).execute();
        st.db.table("transactions").insert(m("id", Store.id(), "user_id", s(user.get("id")), "type", "bid", "amount", amt,
            "note", "Bid on: " + a.get("title"), "auction_id", id, "created_at", bid.get("created_at"))).execute();
        st.log("bid_placed", s(user.get("id")), ip(req), m("auction_id", id, "amount", amt));
        try {
            socket.emitToRoom("auction:" + id, "bid_update", m("auction_id", id, "current_bid", amt, "current_bid_inr", "₹" + String.format("%,d", amt / 100),
                "bid_count", lng(a.get("bid_count")) + 1, "bidder", user.get("username"), "timestamp", bid.get("created_at")));
        } catch (Exception ignored) {}
        return ResponseEntity.status(201).body(m("message", "Bid placed successfully",
            "bid", m("id", s(bid.get("id")), "amount", amt, "amount_inr", amt / 100.0, "created_at", bid.get("created_at")), "new_wallet_balance", nb));
    }

    @GetMapping("/{id}/bids")
    public Object bids(@PathVariable String id, @RequestParam(defaultValue = "20") int limit) {
        List<Object> out = new ArrayList<>();
        for (var b : st.bidHistory(id, Math.min(limit, 50))) {
            var bidder = st.userById(s(b.get("bidder_id")));
            out.add(m("id", s(b.get("id")), "amount", b.get("amount"), "amount_inr", lng(b.get("amount")) / 100.0,
                "bidder", bidder != null ? bidder.get("username") : "Unknown", "created_at", b.get("created_at")));
        }
        return m("bids", out);
    }
}
