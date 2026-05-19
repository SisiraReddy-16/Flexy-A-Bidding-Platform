"""
Flexy – Audit / security event logging (Supabase)
"""
import uuid
from datetime import datetime, timezone
from database import get_db


def log_event(event_type: str, user_id: str | None, ip: str, meta: dict | None = None) -> None:
    try:
        get_db().table('audit_log').insert({
            'id':         str(uuid.uuid4()),
            'event_type': event_type,
            'user_id':    str(user_id) if user_id else None,
            'ip':         ip,
            'meta':       meta or {},
            'created_at': datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        print(f'[AUDIT] Failed to log {event_type}: {e}')


def get_recent_events(user_id: str, limit: int = 50) -> list:
    r = get_db().table('audit_log').select('*').eq('user_id', str(user_id)).order('created_at', desc=True).limit(limit).execute()
    return r.data or []
