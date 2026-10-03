package in.flexy;

import com.corundumstudio.socketio.*;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.*;

import static in.flexy.Util.*;

/** Real-time layer (port of socket_events.py). Same event names, so the existing frontend works unchanged. */
@Service
public class SocketService {
    private final Store st; private final Mail mail; private final Environment env;
    private SocketIOServer server;
    private final Map<String, Set<UUID>> viewers = new ConcurrentHashMap<>();
    private final Set<String> timers = ConcurrentHashMap.newKeySet();

    public SocketService(Store st, Mail mail, Environment env) { this.st = st; this.mail = mail; this.env = env; }

    @PostConstruct
    void start() {
        Configuration c = new Configuration();
        c.setHostname("0.0.0.0");
        c.setPort(Integer.parseInt(env.getProperty("SOCKET_PORT", "9092")));
        c.setOrigin(null);               // allow any origin (same as cors_allowed_origins='*')
        c.setPingTimeout(60000); c.setPingInterval(25000);
        server = new SocketIOServer(c);

        server.addConnectListener(cl -> { var u = userOf(cl); if (u != null) cl.joinRoom("user:" + s(u.get("id"))); });
        server.addDisconnectListener(cl -> viewers.forEach((aid, set) -> {
            if (set.remove(cl.getSessionId())) room("auction:" + aid, "viewer_count", m("auction_id", aid, "count", set.size()));
        }));

        server.addEventListener("join_auction", Map.class, (cl, data, ack) -> {
            String aid = s(data.get("auction_id")); var a = st.getAuction(aid);
            if (a == null) { cl.sendEvent("error", m("message", "Auction not found")); return; }
            cl.joinRoom("auction:" + aid);
            var set = viewers.computeIfAbsent(aid, k -> ConcurrentHashMap.newKeySet()); set.add(cl.getSessionId());
            int count = set.size();
            try { st.db.table("auctions").update(m("view_count", lng(a.get("view_count")) + 1)).eq("id", aid).execute(); } catch (Exception ignored) {}
            var ends = parse(a.get("ends_at"));
            if ("active".equals(a.get("status")) && ends != null && nowDt().isAfter(ends)) { closeAuction(aid, a); a.put("status", "ended"); }
            cl.sendEvent("auction_state", m("auction", st.safeAuction(a), "viewer_count", count));
            room("auction:" + aid, "viewer_count", m("auction_id", aid, "count", count));
            List<Object> hist = new ArrayList<>();
            for (var b : st.bidHistory(aid, 15)) {
                var bu = st.userById(s(b.get("bidder_id")));
                hist.add(m("bidder", bu != null ? bu.get("username") : "Unknown", "amount", b.get("amount"), "created_at", b.get("created_at")));
            }
            cl.sendEvent("bid_history", m("bids", hist));
            ensureTimer(aid);
        });

        server.addEventListener("leave_auction", Map.class, (cl, data, ack) -> {
            String aid = s(data.get("auction_id")); cl.leaveRoom("auction:" + aid);
            var set = viewers.get(aid);
            if (set != null) { set.remove(cl.getSessionId()); room("auction:" + aid, "viewer_count", m("auction_id", aid, "count", set.size())); }
        });

        server.addEventListener("place_bid", Map.class, (cl, data, ack) -> {
            var user = userOf(cl);
            if (user == null) { err(cl, "Authentication required"); return; }
            if (!Boolean.TRUE.equals(user.get("is_email_verified"))) { err(cl, "Please verify your email to bid"); return; }
            String aid = s(data.get("auction_id")); double inr; long amt;
            try { inr = Double.parseDouble(s(data.get("amount_inr"))); amt = Math.round(inr * 100); } catch (Exception e) { err(cl, "Invalid amount"); return; }
            if (amt <= 0) { err(cl, "Bid must be positive"); return; }
            var a = st.getAuction(aid);
            if (a == null) { err(cl, "Auction not found"); return; }
            if (s(a.get("created_by")).equals(s(user.get("id")))) { err(cl, "You cannot bid on your own auction"); return; }
            var ends = parse(a.get("ends_at"));
            if (ends != null && nowDt().isAfter(ends)) { err(cl, "Auction has ended"); return; }
            if (lng(user.get("wallet_balance")) < amt) { err(cl, "Insufficient wallet balance"); return; }
            Object prev = a.get("current_bidder");
            Map<String, Object> bid;
            try { bid = st.placeBid(aid, s(user.get("id")), amt); } catch (IllegalArgumentException e) { err(cl, e.getMessage()); return; }
            long nb = lng(user.get("wallet_balance")) - amt;
            st.db.table("users").update(m("wallet_balance", nb)).eq("id", s(user.get("id"))).execute();
            st.db.table("transactions").insert(m("id", Store.id(), "user_id", s(user.get("id")), "type", "bid", "amount", amt,
                "note", "Bid on: " + a.get("title"), "auction_id", aid, "created_at", bid.get("created_at"))).execute();
            st.log("bid_placed", s(user.get("id")), "127.0.0.1", m("auction_id", aid, "amount", amt));
            if (prev != null && !s(prev).equals(s(user.get("id"))))
                notifyUser(s(prev), "outbid", "⚡ You've been outbid!",
                    "Someone bid ₹" + String.format("%,.0f", inr) + " on \"" + a.get("title") + "\". Bid higher to reclaim the lead!", m("auction_id", aid));
            room("auction:" + aid, "bid_update", m("auction_id", aid, "current_bid", amt, "current_bid_inr", "₹" + String.format("%,.0f", inr),
                "bid_count", lng(a.get("bid_count")) + 1, "bidder", user.get("username"), "timestamp", bid.get("created_at")));
            var fresh = st.userById(s(user.get("id")));
            cl.sendEvent("bid_success", m("message", "Bid placed!", "amount", amt, "new_balance", fresh != null ? lng(fresh.get("wallet_balance")) : 0));
        });
        server.start();
        System.out.println("[SOCKET] Socket.IO server on port " + c.getPort());
    }

    @PreDestroy void stop() { if (server != null) server.stop(); }

    private void err(SocketIOClient c, String msg) { c.sendEvent("bid_error", m("message", msg)); }

    private Map<String, Object> userOf(SocketIOClient c) {
        try {
            String token = null, ck = c.getHandshakeData().getHttpHeaders().get("Cookie");
            if (ck != null) for (String p : ck.split(";")) { p = p.trim(); if (p.startsWith(Auth.COOKIE + "=")) token = p.substring(Auth.COOKIE.length() + 1); }
            if (token == null) token = c.getHandshakeData().getSingleUrlParam("token");
            if (token == null) return null;
            var sess = st.getSession(token);
            return sess == null ? null : st.userById(s(sess.get("user_id")));
        } catch (Exception e) { return null; }
    }

    public void emitToRoom(String room, String event, Object data) { room(room, event, data); }
    private void room(String room, String event, Object data) { if (server != null) server.getRoomOperations(room).sendEvent(event, data); }

    private void notifyUser(String uid, String type, String title, String body, Map<String, Object> meta) {
        var n = st.createNotification(uid, type, title, body, meta);
        room("user:" + uid, "notification", m("id", s(n.get("id")), "type", type, "title", title, "body", body, "meta", meta));
    }

    private void ensureTimer(String aid) {
        if (!timers.add(aid)) return;
        Thread t = new Thread(() -> {
            boolean warned = false;
            try {
                while (true) {
                    var a = st.getAuction(aid);
                    if (a == null || !"active".equals(a.get("status"))) break;
                    var ends = parse(a.get("ends_at"));
                    double left = ends == null ? 0 : java.time.Duration.between(nowDt(), ends).toMillis() / 1000.0;
                    if (left <= 0) { closeAuction(aid, a); break; }
                    if (!warned && left <= 300) { warned = true; endingSoon(aid, a); }
                    room("auction:" + aid, "timer_update", m("auction_id", aid, "seconds_left", (int) left));
                    Thread.sleep(1000);
                }
            } catch (Exception e) { System.out.println("[TIMER] " + e); }
            finally { timers.remove(aid); }
        }, "timer-" + aid);
        t.setDaemon(true); t.start();
    }

    private void closeAuction(String aid, Map<String, Object> auction) {
        st.endAuction(aid);
        var fresh = st.getAuction(aid);
        Object winnerId = fresh != null ? fresh.get("current_bidder") : null;
        long finalBid = fresh != null ? lng(fresh.get("current_bid")) : 0;
        String title = s(auction.getOrDefault("title", "Auction")), winnerName = null, orderId = null;
        if (winnerId != null) {
            var w = st.userById(s(winnerId));
            if (w != null) {
                winnerName = s(w.get("username"));
                orderId = s(st.createOrder(s(winnerId), aid, finalBid).get("id"));
                try { mail.sendAuctionWon(s(w.get("email")), winnerName, title, finalBid, orderId); } catch (Exception e) { System.out.println("[MAIL] " + e); }
                notifyUser(s(winnerId), "auction_won", "🏆 You won the auction!",
                    "Congratulations! You won \"" + title + "\" with a bid of ₹" + String.format("%,.0f", finalBid / 100.0) + "!",
                    m("auction_id", aid, "final_bid", finalBid, "order_id", orderId, "action_url", "/order/" + orderId));
            }
        }
        room("auction:" + aid, "auction_ended", m("auction_id", aid, "winner", winnerName != null ? winnerName : "No winner", "final_bid", finalBid,
            "final_bid_inr", "₹" + String.format("%,.0f", finalBid / 100.0), "order_id", orderId));
    }

    private void endingSoon(String aid, Map<String, Object> a) {
        for (var w : st.db.table("watchlist").select("user_id").eq("auction_id", aid).execute().data())
            notifyUser(s(w.get("user_id")), "auction_ending_soon", "⏰ Auction ending soon!",
                "\"" + a.getOrDefault("title", "Auction") + "\" ends in under 5 minutes. Place your final bid now!", m("auction_id", aid));
    }
}
