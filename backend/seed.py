"""
Flexy – Dataset seeder
Fixes:
  1. Deletes in correct FK order: watchlist → orders → bids → auctions
     (previously crashed because orders.auction_id FK blocked auction delete)
  2. All auction timestamps computed relative to NOW() — no stale CSV dates
  3. Skips rows that error individually instead of crashing everything
Run:  cd backend && python seed.py
"""
import os, uuid, csv, pathlib
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# ── Load env BEFORE any app imports ──────────────────────────────────────────
load_dotenv(pathlib.Path(__file__).parent / '.env', override=True)

from database import init_db, get_db
from models.user_model import find_user_by_email, hash_password


class _App:
    config = {
        'SUPABASE_URL': os.getenv('SUPABASE_URL', ''),
        'SUPABASE_KEY': os.getenv('SUPABASE_KEY', ''),
    }

init_db(_App())
db  = get_db()
now = datetime.now(timezone.utc)

# CSV is one level up from backend/, or inside backend/
_here    = pathlib.Path(__file__).parent
CSV_PATH = _here.parent / 'flexy_bidding_dataset.csv'
if not CSV_PATH.exists():
    CSV_PATH = _here / 'flexy_bidding_dataset.csv'


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_price(s: str) -> int:
    """'1,48,700'  →  paise (int * 100)"""
    return int(s.replace(',', '').replace('"', '').strip()) * 100


def csv_status(s: str) -> str:
    return {'LIVE': 'active', 'UPCOMING': 'upcoming', 'ENDED': 'ended'}.get(
        s.upper().strip(), 'active'
    )


def varied_hours(product_id: str, lo: int, hi: int) -> int:
    """Deterministic but varied offset derived from product number."""
    n = int(''.join(filter(str.isdigit, product_id)) or '1')
    return lo + (n % (hi - lo + 1))


# ── Main ──────────────────────────────────────────────────────────────────────

def seed():
    global db, now
    # Re-initialize in case this is called from within Flask app context
    # (AUTO_SEED or /api/admin/seed endpoint)
    try:
        from flask import current_app
        if current_app:
            db  = get_db()
            now = datetime.now(timezone.utc)
    except RuntimeError:
        pass  # Not in app context — use module-level db/now from __main__

    print('\n[SEED] Starting Flexy seeder ...\n')

    # ── 0. Check if a re-seed is actually needed ──────────────────────────────
    # If there are already active/upcoming auctions, skip to avoid wiping live data
    try:
        existing = db.table('auctions').select('id,status,ends_at').execute().data or []
        active_count = sum(1 for a in existing if a.get('status') in ('active', 'upcoming'))
        if active_count > 0:
            print(f'[SEED] {active_count} active/upcoming auctions already exist — skipping seed.')
            print('[SEED] To force re-seed: POST /api/admin/seed with X-Seed-Secret header, OR')
            print('[SEED] delete all auctions from Supabase then redeploy.')
            return
    except Exception as e:
        print(f'[SEED] Could not check existing auctions: {e}')

    print('[SEED] No active auctions found — seeding fresh data ...')

    # ── 1. Ensure demo user ───────────────────────────────────────────────────
    email = 'demo@flexy.in'
    user  = find_user_by_email(email)
    if not user:
        db.table('users').insert({
            'id':                    str(uuid.uuid4()),
            'email':                 email,
            'username':              'flexy_demo',
            'password_hash':         hash_password('Demo@1234'),
            'is_email_verified':     True,
            'is_seller_verified':    True,
            'kyc_status':            'approved',
            'wallet_balance':        500_000_00,
            'role':                  'user',
            'is_locked':             False,
            'failed_login_attempts': 0,
            'mfa_enabled':           False,
            'avatar_url':            '',
            'bio':                   'Flexy official demo seller',
            'location':              'Hyderabad, India',
            'created_at':            now.isoformat(),
            'updated_at':            now.isoformat(),
        }).execute()
        user = find_user_by_email(email)
        print(f'[SEED] Created demo user: {email} / Demo@1234')
    else:
        print(f'[SEED] Demo user already exists: {email}')

    uid = str(user['id'])

    # ── 2. Delete in correct FK order ─────────────────────────────────────────
    #  orders.auction_id  references  auctions.id   → delete orders FIRST
    #  bids.auction_id    references  auctions.id   → delete bids BEFORE auctions
    print('[SEED] Clearing existing data ...')

    _DUMMY = '00000000-0000-0000-0000-000000000000'

    for table in ('watchlist', 'orders', 'bids', 'auctions'):
        try:
            db.table(table).delete().neq('id', _DUMMY).execute()
            print(f'[SEED]   {table} cleared')
        except Exception as e:
            print(f'[SEED]   {table} clear skipped ({e})')

    # ── 3. Read CSV ───────────────────────────────────────────────────────────
    if not CSV_PATH.exists():
        print(f'[SEED] ERROR: CSV not found at {CSV_PATH}')
        return

    rows = list(csv.DictReader(open(CSV_PATH, encoding='utf-8-sig')))
    print(f'\n[SEED] Inserting {len(rows)} auctions ...\n')

    ok = err = live_n = upcoming_n = ended_n = 0

    for r in rows:
        pid = r.get('product_id', '').strip()
        try:
            base_price  = parse_price(r['base_price_inr'])
            current_bid = parse_price(r['current_bid_inr'])
            total_bids  = int(r.get('total_bids', 0))
            status_csv  = csv_status(r.get('status', 'LIVE'))
            is_featured = int(''.join(filter(str.isdigit, pid)) or '99') <= 5

            # ── Compute fresh timestamps relative to NOW ──────────────────────
            if status_csv == 'ended':
                h_ago     = varied_hours(pid, 24, 168)       # ended 1–7 days ago
                ends_at   = now - timedelta(hours=h_ago)
                starts_at = ends_at - timedelta(hours=varied_hours(pid, 2, 24))
                status    = 'ended'
                ended_n  += 1

            elif status_csv == 'upcoming':
                h_start    = varied_hours(pid, 6, 72)         # starts 6–72 h from now
                h_dur      = varied_hours(pid, 2, 24)
                starts_at  = now + timedelta(hours=h_start)
                ends_at    = starts_at + timedelta(hours=h_dur)
                status     = 'upcoming'
                upcoming_n += 1

            else:                                              # LIVE / active
                h_end    = varied_hours(pid, 2, 48)           # ends 2–48 h from now
                ends_at  = now + timedelta(hours=h_end)
                starts_at= now - timedelta(hours=varied_hours(pid, 1, 12))
                status   = 'active'
                live_n  += 1

            db.table('auctions').insert({
                'id':             str(uuid.uuid4()),
                'title':          r['product_name'].strip(),
                'description':    r.get('description', '').strip(),
                'category':       r.get('category', 'Other').strip(),
                'image_url':      r.get('image_url', '').strip(),
                'starting_price': base_price,
                'reserve_price':  int(base_price * 0.8),
                'current_bid':    current_bid,
                'current_bidder': None,
                'bid_count':      total_bids,
                'view_count':     varied_hours(pid, 10, 500),
                'status':         status,
                'created_by':     uid,
                'ends_at':        ends_at.isoformat(),
                'tags':           [r.get('category', '').lower().strip(),
                                   r.get('condition', '').lower().strip()],
                'is_featured':    is_featured,
                'created_at':     (now - timedelta(hours=varied_hours(pid, 12, 96))).isoformat(),
                'updated_at':     now.isoformat(),
            }).execute()

            label = {'active': 'LIVE', 'upcoming': 'UPCOMING', 'ended': 'ENDED'}[status]
            print(f'[SEED] {label:8} | {r["product_name"][:52]}')
            ok += 1

        except Exception as e:
            print(f'[SEED] ERROR {pid}: {e}')
            err += 1

    print(f"""
[SEED] =========================================
[SEED]  Inserted : {ok}    Errors : {err}
[SEED]  Live     : {live_n}
[SEED]  Upcoming : {upcoming_n}
[SEED]  Ended    : {ended_n}
[SEED] =========================================
[SEED]  Login: demo@flexy.in / Demo@1234
[SEED] =========================================
""")


if __name__ == '__main__':
    seed()