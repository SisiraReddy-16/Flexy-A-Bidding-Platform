"""
Flexy – Watchlist / Favourites model (Supabase)
"""
import uuid
from datetime import datetime, timezone
from database import get_db


def add_to_watchlist(user_id: str, auction_id: str) -> bool:
    """Returns True if added, False if already exists."""
    db = get_db()
    existing = db.table('watchlist').select('id').eq('user_id', str(user_id)).eq('auction_id', str(auction_id)).execute()
    if existing.data:
        return False
    db.table('watchlist').insert({
        'id':         str(uuid.uuid4()),
        'user_id':    str(user_id),
        'auction_id': str(auction_id),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }).execute()
    return True


def remove_from_watchlist(user_id: str, auction_id: str) -> bool:
    r = get_db().table('watchlist').delete().eq('user_id', str(user_id)).eq('auction_id', str(auction_id)).execute()
    return bool(r.data)


def get_watchlist(user_id: str) -> list:
    r = get_db().table('watchlist').select('*').eq('user_id', str(user_id)).order('created_at', desc=True).execute()
    return r.data or []


def is_watching(user_id: str, auction_id: str) -> bool:
    r = get_db().table('watchlist').select('id').eq('user_id', str(user_id)).eq('auction_id', str(auction_id)).execute()
    return bool(r.data)
