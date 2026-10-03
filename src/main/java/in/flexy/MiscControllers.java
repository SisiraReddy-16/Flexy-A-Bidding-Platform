package in.flexy;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.*;

import static in.flexy.Util.*;

/** Notifications, watchlist and orders. */
@RestController
@RequestMapping("/api/notifications")
class NotificationController {
    private final Store st; private final Auth auth;
    NotificationController(Store st, Auth auth) { this.st = st; this.auth = auth; }

    @GetMapping({"", "/"})
    Object list(@RequestParam(defaultValue = "30") int limit, @RequestParam(defaultValue = "") String unread, HttpServletRequest r) {
        String uid = s(auth.user(r).get("id"));
        List<Object> out = new ArrayList<>();
        for (var n : st.notifications(uid, Math.min(limit, 100), unread.equalsIgnoreCase("true"))) out.add(st.safeNotif(n));
        return m("notifications", out, "unread_count", st.unreadCount(uid));
    }
    @PostMapping("/{id}/read")
    Object read(@PathVariable String id, HttpServletRequest r) { st.markRead(s(auth.user(r).get("id")), id); return m("message", "Marked as read"); }
    @PostMapping("/read-all")
    Object readAll(HttpServletRequest r) { st.markAllRead(s(auth.user(r).get("id"))); return m("message", "All notifications marked as read"); }
    @GetMapping({"/count", "/unread"})
    Object count(HttpServletRequest r) { long c = st.unreadCount(s(auth.user(r).get("id"))); return m("count", c, "unread_count", c); }
}

@RestController
@RequestMapping("/api/watchlist")
class WatchlistController {
    private final Store st; private final Auth auth;
    WatchlistController(Store st, Auth auth) { this.st = st; this.auth = auth; }

    @GetMapping({"", "/"})
    Object list(HttpServletRequest r) {
        List<Object> out = new ArrayList<>();
        for (var w : st.watchlist(s(auth.user(r).get("id")))) { var a = st.getAuction(s(w.get("auction_id"))); if (a != null) out.add(st.safeAuction(a)); }
        return m("watchlist", out);
    }
    private Object add(HttpServletRequest r, String aid) {
        aid = aid.trim();
        if (aid.isEmpty()) throw new ApiException(400, "auction_id is required");
        boolean added = st.addWatch(s(auth.user(r).get("id")), aid);
        return m("message", added ? "Added to wishlist" : "Already in wishlist", "added", added);
    }
    private Object remove(HttpServletRequest r, String aid) {
        aid = aid.trim();
        if (aid.isEmpty()) throw new ApiException(400, "auction_id is required");
        return m("message", "Removed from wishlist", "removed", st.removeWatch(s(auth.user(r).get("id")), aid));
    }
    @PostMapping("/add") Object addBody(@RequestBody(required = false) Map<String, Object> b, HttpServletRequest r) { return add(r, s(body(b).get("auction_id"))); }
    @PostMapping("/remove") Object removeBody(@RequestBody(required = false) Map<String, Object> b, HttpServletRequest r) { return remove(r, s(body(b).get("auction_id"))); }
    @GetMapping("/check/{id}") Object check(@PathVariable String id, HttpServletRequest r) { return m("watching", st.isWatching(s(auth.user(r).get("id")), id.trim())); }
    @PostMapping("/{id}") Object addId(@PathVariable String id, HttpServletRequest r) { return add(r, id); }
    @DeleteMapping("/{id}") Object removeId(@PathVariable String id, HttpServletRequest r) { return remove(r, id); }
    @GetMapping("/{id}/status") Object status(@PathVariable String id, HttpServletRequest r) { return m("watching", st.isWatching(s(auth.user(r).get("id")), id.trim())); }
}

@RestController
@RequestMapping("/api/orders")
class OrderController {
    private final Store st; private final Auth auth;
    OrderController(Store st, Auth auth) { this.st = st; this.auth = auth; }

    @GetMapping({"", "/"})
    Object list(HttpServletRequest r) {
        List<Object> out = new ArrayList<>();
        for (var o : st.userOrders(s(auth.user(r).get("id")))) {
            var a = st.getAuction(s(o.get("auction_id")));
            var row = st.safeOrder(o); row.put("auction", a != null ? st.safeAuction(a) : null); out.add(row);
        }
        return m("orders", out);
    }
    @GetMapping("/{id}")
    ResponseEntity<Object> get(@PathVariable String id, HttpServletRequest r) {
        var u = auth.user(r); var o = st.getOrder(id);
        if (o == null) return ResponseEntity.status(404).body(m("error", "Order not found"));
        if (!s(o.get("user_id")).equals(s(u.get("id")))) return ResponseEntity.status(403).body(m("error", "Unauthorised"));
        var a = st.getAuction(s(o.get("auction_id")));
        return ResponseEntity.ok(m("order", st.safeOrder(o), "auction", a != null ? st.safeAuction(a) : null));
    }
    @PostMapping("/{id}/pay")
    @SuppressWarnings("unchecked")
    ResponseEntity<Object> pay(@PathVariable String id, @RequestBody(required = false) Map<String, Object> body, HttpServletRequest r) {
        var u = auth.user(r); var d = body(body);
        String method = s(d.get("method")).trim().toLowerCase();
        Map<String, Object> addr = d.get("address") instanceof Map<?, ?> mp ? (Map<String, Object>) mp : new HashMap<>();
        if (!List.of("cod", "razorpay", "wallet").contains(method)) return ResponseEntity.status(400).body(m("error", "Invalid payment method. Use cod, razorpay, or wallet."));
        if (!truthy(addr.get("full_name")) || !truthy(addr.get("city")) || !truthy(addr.get("pincode")))
            return ResponseEntity.status(400).body(m("error", "Full name, city and pincode are required in address"));
        var o = st.getOrder(id);
        if (o == null) return ResponseEntity.status(404).body(m("error", "Order not found"));
        if (!s(o.get("user_id")).equals(s(u.get("id")))) return ResponseEntity.status(403).body(m("error", "Unauthorised"));
        if (!"pending_payment".equals(o.get("status"))) return ResponseEntity.status(400).body(m("error", "Order has already been processed"));
        if (method.equals("wallet")) {
            long amt = lng(o.get("amount"));
            if (lng(u.get("wallet_balance")) < amt) return ResponseEntity.status(402).body(m("error", "Insufficient wallet balance"));
            st.updateUser(s(u.get("id")), m("wallet_balance", lng(u.get("wallet_balance")) - amt));
            st.db.table("transactions").insert(m("id", Store.id(), "user_id", s(u.get("id")), "type", "order_payment", "amount", amt,
                "note", "Payment for order " + id, "auction_id", s(o.get("auction_id")), "created_at", now())).execute();
        }
        String ns = method.equals("cod") ? "cod" : "paid";
        st.updateOrderStatus(id, ns, method, addr);
        st.log("order_completed", s(u.get("id")), ip(r), m("order_id", id, "method", method));
        return ResponseEntity.ok(m("message", "Order successfully placed!", "status", ns));
    }
}
