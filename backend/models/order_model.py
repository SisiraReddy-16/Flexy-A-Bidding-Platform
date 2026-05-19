"""
Flexy – Order model (Supabase)
"""
import uuid
from datetime import datetime, timezone
from database import get_db


def create_order(user_id: str, auction_id: str, amount_paise: int) -> dict:
    db = get_db()
    order_id = str(uuid.uuid4())
    order = {
        'id':             order_id,
        'user_id':        str(user_id),
        'auction_id':     str(auction_id),
        'amount':         amount_paise,
        'status':         'pending_payment',
        'address':        {},
        'payment_method': None,
        'created_at':     datetime.now(timezone.utc).isoformat(),
        'updated_at':     datetime.now(timezone.utc).isoformat(),
    }
    db.table('orders').insert(order).execute()
    # Link order back to auction
    try:
        db.table('auctions').update({'order_id': order_id}).eq('id', str(auction_id)).execute()
    except Exception:
        pass
    return order


def get_order(order_id: str) -> dict | None:
    try:
        r = get_db().table('orders').select('*').eq('id', str(order_id)).execute()
        return r.data[0] if r.data else None
    except Exception:
        return None


def update_order_status(order_id: str, status: str, method: str, address: dict) -> None:
    get_db().table('orders').update({
        'status':         status,
        'payment_method': method,
        'address':        address,
        'updated_at':     datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(order_id)).execute()


def safe_order(o: dict) -> dict:
    return {
        'id':             str(o['id']),
        'user_id':        str(o['user_id']),
        'auction_id':     str(o['auction_id']),
        'amount':         o['amount'],
        'status':         o['status'],
        'address':        o.get('address', {}),
        'payment_method': o.get('payment_method'),
        'created_at':     o['created_at'],
        'updated_at':     o['updated_at'],
    }


def get_user_orders(user_id: str) -> list:
    r = get_db().table('orders').select('*').eq('user_id', str(user_id)).order('created_at', desc=True).limit(50).execute()
    return r.data or []
