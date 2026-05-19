import uuid
import bcrypt
from datetime import datetime, timezone, timedelta
from database import get_db


# ── Password helpers ─────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── CRUD ─────────────────────────────────────────────────────

def create_user(email: str, username: str, password: str) -> dict:
    import random
    otp   = str(random.randint(100000, 999999))
    expires = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    data  = {
        'id':                          str(uuid.uuid4()),
        'email':                       email.lower().strip(),
        'username':                    username.strip(),
        'password_hash':               hash_password(password),
        'is_email_verified':           False,
        'email_verification_token':    otp,
        'email_verification_expires':  expires,
        'role':                        'user',
        'is_locked':                   False,
        'failed_login_attempts':       0,
        'mfa_enabled':                 False,
        'wallet_balance':              0,
        'avatar_url':                  '',
        'bio':                         '',
        'location':                    '',
        'created_at':                  datetime.now(timezone.utc).isoformat(),
        'updated_at':                  datetime.now(timezone.utc).isoformat(),
    }
    resp = get_db().table('users').insert(data).execute()
    return resp.data[0] if resp.data else data


def find_user_by_email(email: str) -> dict | None:
    r = get_db().table('users').select('*').eq('email', email.lower().strip()).execute()
    return r.data[0] if r.data else None


def find_user_by_id(user_id: str) -> dict | None:
    try:
        r = get_db().table('users').select('*').eq('id', str(user_id)).execute()
        return r.data[0] if r.data else None
    except Exception:
        return None


def find_user_by_username(username: str) -> dict | None:
    r = get_db().table('users').select('*').eq('username', username.strip()).execute()
    return r.data[0] if r.data else None


def find_user_by_verification_token(token: str) -> dict | None:
    r = get_db().table('users').select('*').eq('email_verification_token', token).execute()
    return r.data[0] if r.data else None


def find_user_by_reset_token(token: str) -> dict | None:
    r = get_db().table('users').select('*').eq('password_reset_token', token).execute()
    return r.data[0] if r.data else None


def set_verification_token(user_id: str, token: str) -> None:
    expires = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    get_db().table('users').update({
        'email_verification_token':   token,
        'email_verification_expires': expires,
        'updated_at':                 datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(user_id)).execute()


def mark_email_verified(user_id: str) -> None:
    get_db().table('users').update({
        'is_email_verified':          True,
        'email_verification_token':   None,
        'email_verification_expires': None,
        'updated_at':                 datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(user_id)).execute()


def increment_failed_login(email: str) -> None:
    user = find_user_by_email(email)
    if not user:
        return
    attempts = user.get('failed_login_attempts', 0) + 1
    upd = {'failed_login_attempts': attempts, 'updated_at': datetime.now(timezone.utc).isoformat()}
    if attempts >= 5:
        upd['is_locked']    = True
        upd['locked_until'] = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        upd['failed_login_attempts'] = 0
    get_db().table('users').update(upd).eq('id', user['id']).execute()


def reset_failed_login(user_id: str) -> None:
    get_db().table('users').update({
        'failed_login_attempts': 0,
        'is_locked':             False,
        'locked_until':          None,
        'updated_at':            datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(user_id)).execute()


def update_last_login(user_id: str, ip: str) -> None:
    get_db().table('users').update({
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(user_id)).execute()


def set_reset_token(user_id: str, token: str) -> None:
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    get_db().table('users').update({
        'password_reset_token':   token,
        'password_reset_expires': expires,
        'updated_at':             datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(user_id)).execute()


def update_password(user_id: str, new_password: str) -> None:
    get_db().table('users').update({
        'password_hash':          hash_password(new_password),
        'password_reset_token':   None,
        'password_reset_expires': None,
        'updated_at':             datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(user_id)).execute()


def set_mfa_secret(user_id: str, secret: str) -> None:
    get_db().table('users').update({
        'mfa_secret':  secret,
        'mfa_enabled': True,
        'updated_at':  datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(user_id)).execute()


def disable_mfa(user_id: str) -> None:
    get_db().table('users').update({
        'mfa_enabled': False,
        'mfa_secret':  None,
        'updated_at':  datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(user_id)).execute()


def safe_user(user: dict) -> dict:
    uid = str(user.get('id') or user.get('_id', ''))
    return {
        'id':                 uid,
        '_id':                uid,
        'email':              user['email'],
        'username':           user['username'],
        'role':               user.get('role', 'user'),
        'is_email_verified':  user.get('is_email_verified', False),
        'mfa_enabled':        user.get('mfa_enabled', False),
        'wallet_balance':     user.get('wallet_balance', 0),
        'avatar_url':         user.get('avatar_url', ''),
        'bio':                user.get('bio', ''),
        'location':           user.get('location', ''),
        'is_seller_verified': user.get('is_seller_verified', False),
        'kyc_status':         user.get('kyc_status', 'not_submitted'),
        'created_at':         user.get('created_at', ''),
    }
