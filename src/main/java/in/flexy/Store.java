package in.flexy;

import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;
import java.time.OffsetDateTime;
import java.util.*;

import static in.flexy.Util.*;

/** All data-access logic (port of models/*.py). */
@Service
public class Store {
    final Db db;
    private final BCryptPasswordEncoder enc = new BCryptPasswordEncoder(12);
    private final SecureRandom rnd = new SecureRandom();
    public Store(Db db) { this.db = db; }
    static String id() { return UUID.randomUUID().toString(); }
    private static Map<String, Object> first(Db.Res r) { return r.first(); }

    // ───────── users ─────────
    public String hash(String p) { return enc.encode(p); }
    public boolean verifyPassword(String plain, String hashed) {
        try { return enc.matches(plain, hashed); } catch (Exception e) { return false; }
    }
    public String otp() { return String.valueOf(100000 + rnd.nextInt(900000)); }

    public Map<String, Object> createUser(String email, String username, String password) {
        Map<String, Object> d = m(
            "id", id(), "email", email.toLowerCase().trim(), "username", username.trim(),
            "password_hash", hash(password), "is_email_verified", false,
            "email_verification_token", otp(), "email_verification_expires", nowDt().plusMinutes(10).toString(),
            "role", "user", "is_locked", false, "failed_login_attempts", 0, "mfa_enabled", false,
            "wallet_balance", 0, "avatar_url", "", "bio", "", "location", "",
            "created_at", now(), "updated_at", now());
        var r = db.table("users").insert(d).execute();
        return r.data().isEmpty() ? d : r.data().get(0);
    }
    public Map<String, Object> userByEmail(String e) { return first(db.table("users").select("*").eq("email", e.toLowerCase().trim()).execute()); }
    public Map<String, Object> userById(String id) {
        try { return first(db.table("users").select("*").eq("id", id).execute()); } catch (Exception e) { return null; }
    }
    public Map<String, Object> userByUsername(String u) { return first(db.table("users").select("*").eq("username", u.trim()).execute()); }
    public Map<String, Object> userByVerifyToken(String t) { return first(db.table("users").select("*").eq("email_verification_token", t).execute()); }
    public Map<String, Object> userByResetToken(String t) { return first(db.table("users").select("*").eq("password_reset_token", t).execute()); }
    public void updateUser(String id, Map<String, Object> upd) {
        upd.put("updated_at", now());
        db.table("users").update(upd).eq("id", id).execute();
    }
    public void setVerificationToken(String uid, String token) {
        updateUser(uid, m("email_verification_token", token, "email_verification_expires", nowDt().plusMinutes(10).toString()));
    }
    public void markEmailVerified(String uid) {
        updateUser(uid, m("is_email_verified", true, "email_verification_token", null, "email_verification_expires", null));
    }
    public void incrementFailedLogin(String email) {
        var u = userByEmail(email);
        if (u == null) return;
        long attempts = lng(u.get("failed_login_attempts")) + 1;
        Map<String, Object> upd = m("failed_login_attempts", attempts);
        if (attempts >= 5) {
            upd.put("is_locked", true);
            upd.put("locked_until", nowDt().plusMinutes(30).toString());
            upd.put("failed_login_attempts", 0);
        }
        updateUser(s(u.get("id")), upd);
    }
    public void resetFailedLogin(String uid) {
        updateUser(uid, m("failed_login_attempts", 0, "is_locked", false, "locked_until", null));
    }
    public void updateLastLogin(String uid) { updateUser(uid, new HashMap<>()); }
    public void setResetToken(String uid, String token) {
        updateUser(uid, m("password_reset_token", token, "password_reset_expires", nowDt().plusHours(1).toString()));
    }
    public void updatePassword(String uid, String pw) {
        updateUser(uid, m("password_hash", hash(pw), "password_reset_token", null, "password_reset_expires", null));
    }
    public void setMfaSecret(String uid, String secret) { updateUser(uid, m("mfa_secret", secret, "mfa_enabled", true)); }
    public void disableMfa(String uid) { updateUser(uid, m("mfa_enabled", false, "mfa_secret", null)); }

    public Map<String, Object> safeUser(Map<String, Object> u) {
        String uid = s(u.get("id"));
        return m("id", uid, "_id", uid, "email", u.get("email"), "username", u.get("username"),
            "role", u.getOrDefault("role", "user"), "is_email_verified", u.getOrDefault("is_email_verified", false),
            "mfa_enabled", u.getOrDefault("mfa_enabled", false), "wallet_balance", u.getOrDefault("wallet_balance", 0),
            "avatar_url", u.getOrDefault("avatar_url", ""), "bio", u.getOrDefault("bio", ""),
            "location", u.getOrDefault("location", ""), "is_seller_verified", u.getOrDefault("is_seller_verified", false),
            "kyc_status", u.getOrDefault("kyc_status", "not_submitted"), "created_at", u.getOrDefault("created_at", ""));
    }

    // ───────── sessions ─────────
    public String createSession(String uid, String ip, String ua) {
        byte[] b = new byte[48]; rnd.nextBytes(b);
        String token = Base64.getUrlEncoder().withoutPadding().encodeToString(b);
        db.table("sessions").insert(m("id", id(), "token", token, "user_id", uid, "ip", ip, "user_agent", ua,
            "is_valid", true, "created_at", now(), "expires_at", nowDt().plusHours(24).toString())).execute();
        return token;
    }
    public Map<String, Object> getSession(String token) {
        var s = first(db.table("sessions").select("*").eq("token", token).eq("is_valid", true).execute());
        if (s == null) return null;
        OffsetDateTime exp = parse(s.get("expires_at"));
        if (exp != null && nowDt().isAfter(exp)) { invalidateSession(token); return null; }
        return s;
    }
    public void invalidateSession(String token) { db.table("sessions").update(m("is_valid", false)).eq("token", token).execute(); }
    public void invalidateAllSessions(String uid) { db.table("sessions").update(m("is_valid", false)).eq("user_id", uid).execute(); }
    public List<Map<String, Object>> userSessions(String uid) {
        return db.table("sessions").select("*").eq("user_id", uid).eq("is_valid", true).order("created_at", true).execute().data();
    }

    // ───────── audit ─────────
    public void log(String type, String uid, String ip, Map<String, Object> meta) {
        try {
            db.table("audit_log").insert(m("id", id(), "event_type", type, "user_id", uid, "ip", ip,
                "meta", meta == null ? new HashMap<>() : meta, "created_at", now())).execute();
        } catch (Exception e) { System.out.println("[AUDIT] Failed to log " + type + ": " + e.getMessage()); }
    }
    public void log(String type, String uid, String ip) { log(type, uid, ip, null); }
    public List<Map<String, Object>> recentEvents(String uid) {
        return db.table("audit_log").select("*").eq("user_id", uid).order("created_at", true).limit(50).execute().data();
    }

    // ───────── notifications ─────────
    public Map<String, Object> createNotification(String uid, String type, String title, String body, Map<String, Object> meta) {
        var n = m("id", id(), "user_id", uid, "type", type, "title", title, "body", body,
            "meta", meta == null ? new HashMap<>() : meta, "read", false, "created_at", now());
        db.table("notifications").insert(n).execute();
        return n;
    }
    public List<Map<String, Object>> notifications(String uid, int limit, boolean unreadOnly) {
        var q = db.table("notifications").select("*").eq("user_id", uid);
        if (unreadOnly) q = q.eq("read", false);
        return q.order("created_at", true).limit(limit).execute().data();
    }
    public void markRead(String uid, String nid) { db.table("notifications").update(m("read", true)).eq("id", nid).eq("user_id", uid).execute(); }
    public void markAllRead(String uid) { db.table("notifications").update(m("read", true)).eq("user_id", uid).execute(); }
    public long unreadCount(String uid) {
        Long c = db.table("notifications").selectCount("id").eq("user_id", uid).eq("read", false).execute().count();
        return c == null ? 0 : c;
    }
    public Map<String, Object> safeNotif(Map<String, Object> n) {
        return m("id", s(n.get("id")), "type", n.get("type"), "title", n.get("title"), "body", n.get("body"),
            "meta", n.getOrDefault("meta", new HashMap<>()), "read", n.get("read"), "created_at", n.get("created_at"));
    }

    // ───────── orders ─────────
    public Map<String, Object> createOrder(String uid, String auctionId, long amount) {
        String oid = id();
        var o = m("id", oid, "user_id", uid, "auction_id", auctionId, "amount", amount, "status", "pending_payment",
            "address", new HashMap<>(), "payment_method", null, "created_at", now(), "updated_at", now());
        db.table("orders").insert(o).execute();
        try { db.table("auctions").update(m("order_id", oid)).eq("id", auctionId).execute(); } catch (Exception ignored) {}
        return o;
    }
    public Map<String, Object> getOrder(String oid) {
        try { return first(db.table("orders").select("*").eq("id", oid).execute()); } catch (Exception e) { return null; }
    }
    public void updateOrderStatus(String oid, String status, String method, Object address) {
        db.table("orders").update(m("status", status, "payment_method", method, "address", address, "updated_at", now())).eq("id", oid).execute();
    }
    public Map<String, Object> safeOrder(Map<String, Object> o) {
        return m("id", s(o.get("id")), "user_id", s(o.get("user_id")), "auction_id", s(o.get("auction_id")),
            "amount", o.get("amount"), "status", o.get("status"), "address", o.getOrDefault("address", new HashMap<>()),
            "payment_method", o.get("payment_method"), "created_at", o.get("created_at"), "updated_at", o.get("updated_at"));
    }
    public List<Map<String, Object>> userOrders(String uid) {
        return db.table("orders").select("*").eq("user_id", uid).order("created_at", true).limit(50).execute().data();
    }

    // ───────── watchlist ─────────
    public boolean addWatch(String uid, String aid) {
        if (!db.table("watchlist").select("id").eq("user_id", uid).eq("auction_id", aid).execute().data().isEmpty()) return false;
        db.table("watchlist").insert(m("id", id(), "user_id", uid, "auction_id", aid, "created_at", now())).execute();
        return true;
    }
    public boolean removeWatch(String uid, String aid) {
        return !db.table("watchlist").delete().eq("user_id", uid).eq("auction_id", aid).execute().data().isEmpty();
    }
    public List<Map<String, Object>> watchlist(String uid) {
        return db.table("watchlist").select("*").eq("user_id", uid).order("created_at", true).execute().data();
    }
    public boolean isWatching(String uid, String aid) {
        return !db.table("watchlist").select("id").eq("user_id", uid).eq("auction_id", aid).execute().data().isEmpty();
    }

    // ───────── auctions / bids ─────────
    public Map<String, Object> createAuction(Map<String, Object> d, String creator) {
        long sp = lng(d.get("starting_price"));
        var a = m("id", id(), "title", d.get("title"), "description", d.getOrDefault("description", ""),
            "category", d.getOrDefault("category", "Other"), "image_url", d.getOrDefault("image_url", ""),
            "starting_price", sp, "reserve_price", lng(d.get("reserve_price")), "current_bid", sp, "current_bidder", null,
            "bid_count", 0, "view_count", 0, "status", "active", "created_by", creator, "ends_at", s(d.get("ends_at")),
            "tags", d.getOrDefault("tags", new ArrayList<>()), "is_featured", false, "created_at", now(), "updated_at", now());
        var r = db.table("auctions").insert(a).execute();
        return r.data().isEmpty() ? a : r.data().get(0);
    }
    public Map<String, Object> getAuction(String id) {
        try { return first(db.table("auctions").select("*").eq("id", id).execute()); } catch (Exception e) { return null; }
    }
    public Map<String, Object> placeBid(String auctionId, String bidderId, long amt) {
        var a = getAuction(auctionId);
        if (a == null) throw new IllegalArgumentException("Auction not found");
        if (!"active".equals(a.get("status"))) throw new IllegalArgumentException("Auction is not active");
        OffsetDateTime ends = parse(a.get("ends_at"));
        if (ends != null && nowDt().isAfter(ends)) throw new IllegalArgumentException("Auction has ended");
        if (amt <= lng(a.get("current_bid"))) throw new IllegalArgumentException("Bid must exceed current bid");
        var res = db.table("auctions").update(m("current_bid", amt, "current_bidder", bidderId,
                "bid_count", lng(a.get("bid_count")) + 1, "updated_at", now()))
            .eq("id", auctionId).eq("status", "active").lt("current_bid", amt).execute();
        if (res.data().isEmpty()) throw new IllegalArgumentException("Bid race condition — someone placed a higher bid. Please refresh.");
        var bid = m("id", id(), "auction_id", auctionId, "bidder_id", bidderId, "amount", amt, "created_at", now());
        db.table("bids").insert(bid).execute();
        return bid;
    }
    public List<Map<String, Object>> bidHistory(String auctionId, int limit) {
        return db.table("bids").select("*").eq("auction_id", auctionId).order("created_at", true).limit(limit).execute().data();
    }
    public void endAuction(String id) { db.table("auctions").update(m("status", "ended", "updated_at", now())).eq("id", id).execute(); }

    public Map<String, Object> safeAuction(Map<String, Object> a) {
        String ends = s(a.get("ends_at"));
        if (ends.endsWith("Z")) ends = ends.substring(0, ends.length() - 1) + "+00:00";
        return m("id", s(a.get("id")), "title", a.get("title"), "description", a.getOrDefault("description", ""),
            "category", a.getOrDefault("category", ""), "image_url", a.getOrDefault("image_url", ""),
            "starting_price", a.get("starting_price"), "reserve_price", a.getOrDefault("reserve_price", 0),
            "current_bid", a.get("current_bid"), "bid_count", a.getOrDefault("bid_count", 0),
            "view_count", a.getOrDefault("view_count", 0), "status", a.get("status"), "created_by", s(a.get("created_by")),
            "ends_at", ends, "starts_at", a.getOrDefault("starts_at", ""), "created_at", a.getOrDefault("created_at", ""),
            "tags", a.getOrDefault("tags", new ArrayList<>()), "is_featured", a.getOrDefault("is_featured", false),
            "order_id", a.get("order_id") != null ? s(a.get("order_id")) : null,
            "winner_id", a.get("current_bidder") != null ? s(a.get("current_bidder")) : null);
    }
}
