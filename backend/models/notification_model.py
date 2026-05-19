"""
Flexy – Notification model (Supabase)
"""
import uuid
from datetime import datetime, timezone
from database import get_db


def create_notification(user_id: str, notif_type: str, title: str, body: str, meta: dict = None) -> dict:
    n = {
        'id':         str(uuid.uuid4()),
        'user_id':    str(user_id),
        'type':       notif_type,
        'title':      title,
        'body':       body,
        'meta':       meta or {},
        'read':       False,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    get_db().table('notifications').insert(n).execute()
    return n


def get_notifications(user_id: str, limit: int = 30, unread_only: bool = False) -> list:
    q = get_db().table('notifications').select('*').eq('user_id', str(user_id))
    if unread_only:
        q = q.eq('read', False)
    r = q.order('created_at', desc=True).limit(limit).execute()
    return r.data or []


def mark_read(notif_id: str) -> None:
    get_db().table('notifications').update({'read': True}).eq('id', str(notif_id)).execute()


def mark_all_read(user_id: str) -> None:
    get_db().table('notifications').update({'read': True}).eq('user_id', str(user_id)).execute()


def unread_count(user_id: str) -> int:
    r = get_db().table('notifications').select('id', count='exact').eq('user_id', str(user_id)).eq('read', False).execute()
    return r.count or 0


def safe_notif(n: dict) -> dict:
    return {
        'id':         str(n['id']),
        'type':       n['type'],
        'title':      n['title'],
        'body':       n['body'],
        'meta':       n.get('meta', {}),
        'read':       n['read'],
        'created_at': n['created_at'],
    }
