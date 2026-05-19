"""
Flexy – Session management (Supabase)
"""
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from database import get_db

SESSION_TTL_HOURS = 24


def create_session(user_id: str, ip: str, user_agent: str) -> str:
    token = secrets.token_urlsafe(48)
    get_db().table('sessions').insert({
        'id':         str(uuid.uuid4()),
        'token':      token,
        'user_id':    str(user_id),
        'ip':         ip,
        'user_agent': user_agent,
        'is_valid':   True,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'expires_at': (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).isoformat(),
    }).execute()
    return token


def get_session(token: str) -> dict | None:
    r = get_db().table('sessions').select('*').eq('token', token).eq('is_valid', True).execute()
    if not r.data:
        return None
    session = r.data[0]
    exp_str = session['expires_at']
    if exp_str.endswith('Z'):
        exp_str = exp_str[:-1] + '+00:00'
    exp = datetime.fromisoformat(exp_str)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        invalidate_session(token)
        return None
    return session


def invalidate_session(token: str) -> None:
    get_db().table('sessions').update({'is_valid': False}).eq('token', token).execute()


def invalidate_all_user_sessions(user_id: str) -> None:
    get_db().table('sessions').update({'is_valid': False}).eq('user_id', str(user_id)).execute()


def get_all_user_sessions(user_id: str) -> list:
    r = get_db().table('sessions').select('*').eq('user_id', str(user_id)).eq('is_valid', True).order('created_at', desc=True).execute()
    return r.data or []
