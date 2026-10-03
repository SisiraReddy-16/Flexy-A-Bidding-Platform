package in.flexy;

import org.apache.commons.csv.*;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.*;

import static in.flexy.Util.*;

/** Dataset seeder (port of seed.py). Runs at startup if AUTO_SEED=true, or via POST /api/admin/seed. */
@Component
public class Seeder implements ApplicationRunner {
    private final Store st; private final Environment env;
    public Seeder(Store st, Environment env) { this.st = st; this.env = env; }

    @Override public void run(ApplicationArguments args) {
        if ("true".equals(env.getProperty("AUTO_SEED"))) {
            try { seed(); System.out.println("[APP] Auto-seed completed."); } catch (Exception e) { System.out.println("[APP] Auto-seed skipped: " + e); }
        }
    }

    static long price(String s) { return Long.parseLong(s.replace(",", "").replace("\"", "").trim()) * 100; }
    static int hours(String pid, int lo, int hi) {
        String d = pid.replaceAll("\\D", ""); int n = d.isEmpty() ? 1 : Integer.parseInt(d);
        return lo + (n % (hi - lo + 1));
    }

    public synchronized void seed() throws Exception {
        var db = st.db; OffsetDateTime now = nowDt();
        System.out.println("\n[SEED] Starting Flexy seeder ...\n");
        try {
            long active = db.table("auctions").select("id,status").execute().data().stream()
                .filter(a -> "active".equals(a.get("status")) || "upcoming".equals(a.get("status"))).count();
            if (active > 0) { System.out.println("[SEED] " + active + " active/upcoming auctions already exist — skipping seed."); return; }
        } catch (Exception e) { System.out.println("[SEED] Could not check existing auctions: " + e.getMessage()); }

        String email = "demo@flexy.in"; var user = st.userByEmail(email);
        if (user == null) {
            db.table("users").insert(m("id", Store.id(), "email", email, "username", "flexy_demo", "password_hash", st.hash("Demo@1234"),
                "is_email_verified", true, "is_seller_verified", true, "kyc_status", "approved", "wallet_balance", 50_000_000L, "role", "user",
                "is_locked", false, "failed_login_attempts", 0, "mfa_enabled", false, "avatar_url", "", "bio", "Flexy official demo seller",
                "location", "Hyderabad, India", "created_at", now.toString(), "updated_at", now.toString())).execute();
            user = st.userByEmail(email);
            System.out.println("[SEED] Created demo user: " + email + " / Demo@1234");
        }
        String uid = s(user.get("id")); String dummy = "00000000-0000-0000-0000-000000000000";
        for (String t : new String[]{"watchlist", "orders", "bids", "auctions"}) {
            try { db.table(t).delete().neq("id", dummy).execute(); } catch (Exception e) { System.out.println("[SEED]   " + t + " clear skipped (" + e.getMessage() + ")"); }
        }
        InputStream in = getClass().getResourceAsStream("/flexy_bidding_dataset.csv");
        if (in == null) { System.out.println("[SEED] ERROR: CSV not found"); return; }
        int ok = 0, err = 0;
        try (PushbackReader rd = new PushbackReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            int first = rd.read(); if (first != 0xFEFF && first != -1) rd.unread(first);   // strip BOM
            for (CSVRecord r : CSVFormat.DEFAULT.builder().setHeader().setSkipHeaderRecord(true).build().parse(rd)) {
                String pid = r.get("product_id").trim().replace("\uFEFF", "");
                try {
                    long base = price(r.get("base_price_inr")), cur = price(r.get("current_bid_inr"));
                    String csv = r.get("status").trim().toUpperCase();
                    String status = csv.equals("ENDED") ? "ended" : csv.equals("UPCOMING") ? "upcoming" : "active";
                    String d = pid.replaceAll("\\D", ""); boolean featured = Integer.parseInt(d.isEmpty() ? "99" : d) <= 5;
                    OffsetDateTime ends;
                    if (status.equals("ended")) ends = now.minusHours(hours(pid, 24, 168));
                    else if (status.equals("upcoming")) ends = now.plusHours(hours(pid, 6, 72) + hours(pid, 2, 24));
                    else ends = now.plusHours(hours(pid, 2, 48));
                    String cat = r.get("category").trim();
                    db.table("auctions").insert(m("id", Store.id(), "title", r.get("product_name").trim(), "description", r.get("description").trim(),
                        "category", cat, "image_url", r.get("image_url").trim(), "starting_price", base, "reserve_price", (long) (base * 0.8),
                        "current_bid", cur, "current_bidder", null, "bid_count", Integer.parseInt(r.get("total_bids").trim()),
                        "view_count", hours(pid, 10, 500), "status", status, "created_by", uid, "ends_at", ends.toString(),
                        "tags", List.of(cat.toLowerCase(), r.get("condition").trim().toLowerCase()), "is_featured", featured,
                        "created_at", now.minusHours(hours(pid, 12, 96)).toString(), "updated_at", now.toString())).execute();
                    ok++;
                } catch (Exception e) { System.out.println("[SEED] ERROR " + pid + ": " + e.getMessage()); err++; }
            }
        }
        System.out.println("[SEED] Inserted: " + ok + "  Errors: " + err + "\n[SEED] Login: demo@flexy.in / Demo@1234");
    }
}
