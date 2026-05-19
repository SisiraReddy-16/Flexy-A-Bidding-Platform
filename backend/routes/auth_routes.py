import secrets
import os
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g, make_response

from middleware.auth_middleware import jwt_required
from extensions import limiter
from middleware.validation import validate_email, validate_password, validate_username
from models.user_model import (
    create_user, find_user_by_email, find_user_by_id,
    find_user_by_verification_token, find_user_by_reset_token,
    mark_email_verified, increment_failed_login, reset_failed_login,
    set_reset_token, update_password, update_last_login,
    set_mfa_secret, disable_mfa, verify_password, safe_user,
    find_user_by_username, set_verification_token,
)
from models.session_model import (
    create_session, invalidate_session, invalidate_all_user_sessions,
    get_all_user_sessions,
)
from models.audit_model import log_event
from services.email_service import (
    send_verification_email, send_password_reset_email, send_login_alert_email,
)
from services.mfa_service import generate_mfa_secret, get_totp_uri, generate_qr_base64, verify_totp

auth_bp = Blueprint('auth', __name__)

SESSION_COOKIE = 'flexy_session'
IS_PROD        = os.getenv('FLASK_ENV') == 'production'
_DUMMY_HASH    = '$2b$12$wXvhavbM/xMS6WBYV6Et7.pZXoNHjM5XYbr3Erjmjig1qOAw2dMVy'


def _set_cookie(response, token: str):
    response.set_cookie(
        SESSION_COOKIE, token,
        httponly=True, secure=IS_PROD,
        samesite='Lax', max_age=86400, path='/',
    )
    return response


def _clear_cookie(response):
    response.delete_cookie(SESSION_COOKIE, path='/')
    return response


def _ip() -> str:
    return request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()


def _parse_dt(dt_str):
    """Parse ISO datetime string ensuring timezone awareness."""
    if not dt_str:
        return None
    if isinstance(dt_str, datetime):
        return dt_str if dt_str.tzinfo else dt_str.replace(tzinfo=timezone.utc)
    if dt_str.endswith('Z'):
        dt_str = dt_str[:-1] + '+00:00'
    dt = datetime.fromisoformat(dt_str)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── Signup ────────────────────────────────────────────────────

@auth_bp.route('/signup', methods=['POST'])
@limiter.limit('10 per hour')
def signup():
    data = request.get_json(silent=True) or {}
    try:
        email    = validate_email(data.get('email', ''))
        username = validate_username(data.get('username', ''))
        password = validate_password(data.get('password', ''))
    except ValueError as e:
        return jsonify({'error': str(e)}), 422

    if find_user_by_email(email):
        return jsonify({'message': 'If that email is available, a verification OTP has been sent.'}), 200

    if find_user_by_username(username):
        return jsonify({'error': 'Username already taken'}), 409

    user  = create_user(email, username, password)
    token = user['email_verification_token']
    try:
        send_verification_email(email, username, token)
    except Exception as e:
        print(f'[MAIL] {e}')

    log_event('signup', str(user['id']), _ip())
    return jsonify({'message': 'Account created. Please check your email for the OTP to verify your account.'}), 201


# ── Resend Verification ────────────────────────────────────────

@auth_bp.route('/resend-verification', methods=['POST'])
@limiter.limit('3 per hour')
def resend_verification():
    data = request.get_json(silent=True) or {}
    try:
        email = validate_email(data.get('email', ''))
    except ValueError:
        return jsonify({'message': 'If that email exists, a new OTP has been sent.'}), 200

    user = find_user_by_email(email)
    if user and not user.get('is_email_verified'):
        import random
        token = str(random.randint(100000, 999999))
        set_verification_token(str(user['id']), token)
        try:
            send_verification_email(email, user['username'], token)
        except Exception:
            pass
    return jsonify({'message': 'If that email exists, a new OTP has been sent.'}), 200


# ── Verify OTP ────────────────────────────────────────────────

@auth_bp.route('/verify-otp', methods=['POST'])
@limiter.limit('10 per 15 minutes')
def verify_otp():
    data  = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    otp   = data.get('otp', '').strip()

    if not email or not otp:
        return jsonify({'error': 'Email and OTP are required'}), 400

    user = find_user_by_email(email)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if user.get('is_email_verified'):
        return jsonify({'message': 'Email is already verified.'}), 200

    if user.get('email_verification_token') != otp:
        return jsonify({'error': 'Invalid OTP.'}), 400

    expires = _parse_dt(user.get('email_verification_expires'))
    if expires and datetime.now(timezone.utc) > expires:
        return jsonify({'error': 'OTP has expired. Please request a new one.', 'expired': True, 'email': email}), 400

    mark_email_verified(str(user['id']))
    log_event('email_verified', str(user['id']), _ip())

    ip = _ip()
    ua = request.headers.get('User-Agent', '')[:500]
    reset_failed_login(str(user['id']))
    update_last_login(str(user['id']), ip)
    session_token = create_session(str(user['id']), ip, ua)

    try:
        send_login_alert_email(user['email'], user['username'], ip, ua)
    except Exception:
        pass

    resp = make_response(jsonify({
        'user':    safe_user({**user, 'is_email_verified': True}),
        'message': 'Email verified and logged in successfully.',
    }), 200)
    _set_cookie(resp, session_token)
    return resp

# ── Verify Email via Link (GET) ────────────────────────────
@auth_bp.route('/verify-email', methods=['GET'])
def verify_email_link():
    token = request.args.get('token', '').strip()

    if not token:
        return jsonify({'error': 'No token provided.'}), 400

    user = find_user_by_verification_token(token)
    if not user:
        return jsonify({'error': 'This verification link is invalid or has already been used.'}), 400

    if user.get('is_email_verified'):
        return jsonify({'message': 'Email is already verified.'}), 200

    expires = _parse_dt(user.get('email_verification_expires'))
    if expires and datetime.now(timezone.utc) > expires:
        return jsonify({
            'error':   'This verification link has expired. Please request a new one.',
            'expired': True,
            'email':   user['email'],
        }), 400

    mark_email_verified(str(user['id']))
    log_event('email_verified', str(user['id']), _ip())

    ip = _ip()
    ua = request.headers.get('User-Agent', '')[:500]
    reset_failed_login(str(user['id']))
    update_last_login(str(user['id']), ip)

    return jsonify({'message': 'Your email has been verified! You can now log in.'}), 200

# ── Login ─────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['POST'])
@limiter.limit('5 per 15 minutes')
def login():
    data = request.get_json(silent=True) or {}
    ip   = _ip()
    ua   = request.headers.get('User-Agent', '')[:500]

    try:
        email    = validate_email(data.get('email', ''))
        password = data.get('password', '')
        if not isinstance(password, str) or not password:
            raise ValueError('Password required')
    except ValueError:
        return jsonify({'error': 'Invalid credentials'}), 401

    user      = find_user_by_email(email)
    real_hash = user['password_hash'] if user else _DUMMY_HASH

    try:
        pwd_ok = verify_password(password, real_hash)
    except Exception:
        pwd_ok = False

    if not pwd_ok or not user:
        if user:
            increment_failed_login(email)
            log_event('login_failed', str(user['id']), ip, {'reason': 'bad_password'})
        return jsonify({'error': 'Invalid credentials'}), 401

    if user.get('is_locked'):
        locked_until = _parse_dt(user.get('locked_until'))
        if locked_until and datetime.now(timezone.utc) < locked_until:
            remaining = int((locked_until - datetime.now(timezone.utc)).total_seconds() / 60)
            return jsonify({'error': f'Account locked. Try again in {remaining} minutes.'}), 403
        reset_failed_login(str(user['id']))

    if not user.get('is_email_verified'):
        return jsonify({
            'error':      'Please verify your email before logging in.',
            'unverified': True,
            'email':      email,
        }), 403

    if user.get('mfa_enabled') and user.get('mfa_secret'):
        otp_code = data.get('otp', '')
        if not otp_code:
            return jsonify({'mfa_required': True}), 200
        if not verify_totp(user['mfa_secret'], str(otp_code)):
            log_event('mfa_failed', str(user['id']), ip)
            return jsonify({'error': 'Invalid OTP code. Check your authenticator app.'}), 401

    reset_failed_login(str(user['id']))
    update_last_login(str(user['id']), ip)
    session_token = create_session(str(user['id']), ip, ua)
    log_event('login_success', str(user['id']), ip)

    try:
        send_login_alert_email(user['email'], user['username'], ip, ua)
    except Exception:
        pass

    resp = make_response(jsonify({'user': safe_user(user), 'message': 'Login successful'}), 200)
    _set_cookie(resp, session_token)
    return resp


# ── Logout ────────────────────────────────────────────────────

@auth_bp.route('/logout', methods=['POST'])
@jwt_required
def logout():
    invalidate_session(g.session_token)
    log_event('logout', str(g.current_user['id']), _ip())
    resp = make_response(jsonify({'message': 'Logged out'}), 200)
    _clear_cookie(resp)
    return resp


# ── Forgot Password ───────────────────────────────────────────

@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit('5 per hour')
def forgot_password():
    data = request.get_json(silent=True) or {}
    try:
        email = validate_email(data.get('email', ''))
    except ValueError:
        return jsonify({'message': 'If that email is registered, a reset link has been sent.'}), 200

    user = find_user_by_email(email)
    if user:
        try:
            token = secrets.token_urlsafe(32)
            set_reset_token(str(user['id']), token)
            send_password_reset_email(email, user['username'], token)
            log_event('password_reset_requested', str(user['id']), _ip())
        except Exception:
            pass

    return jsonify({'message': 'If that email is registered, a reset link has been sent.'}), 200


# ── Reset Password ────────────────────────────────────────────

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data     = request.get_json(silent=True) or {}
    token    = data.get('token', '').strip()
    new_pass = data.get('password', '')

    if not token:
        return jsonify({'error': 'Reset token is required'}), 400

    try:
        new_pass = validate_password(new_pass)
    except ValueError as e:
        return jsonify({'error': str(e)}), 422

    user = find_user_by_reset_token(token)
    if not user:
        return jsonify({'error': 'Invalid or expired reset link.'}), 400

    # Check expiry
    expires = _parse_dt(user.get('password_reset_expires'))
    if expires and datetime.now(timezone.utc) > expires:
        return jsonify({'error': 'Reset link has expired. Please request a new one.'}), 400

    update_password(str(user['id']), new_pass)
    invalidate_all_user_sessions(str(user['id']))
    log_event('password_reset_completed', str(user['id']), _ip())
    return jsonify({'message': 'Password updated. All sessions have been logged out.'}), 200


# ── Change Password (logged-in) ────────────────────────────────

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required
def change_password():
    data         = request.get_json(silent=True) or {}
    current_pass = data.get('current_password', '')
    new_pass     = data.get('new_password', '')

    if not current_pass:
        return jsonify({'error': 'Current password required'}), 422

    user = g.current_user
    try:
        pwd_ok = verify_password(current_pass, user['password_hash'])
    except Exception:
        pwd_ok = False

    if not pwd_ok:
        return jsonify({'error': 'Current password is incorrect'}), 401

    try:
        new_pass = validate_password(new_pass)
    except ValueError as e:
        return jsonify({'error': str(e)}), 422

    update_password(str(user['id']), new_pass)
    # Invalidate all sessions except current
    from database import get_db
    db = get_db()
    sessions = db.table('sessions').select('id,token').eq('user_id', str(user['id'])).eq('is_valid', True).execute()
    for s in (sessions.data or []):
        if s['token'] != g.session_token:
            db.table('sessions').update({'is_valid': False}).eq('id', s['id']).execute()

    log_event('password_changed', str(user['id']), _ip())
    return jsonify({'message': 'Password changed successfully. Other sessions logged out.'}), 200


# ── MFA Setup ─────────────────────────────────────────────────

@auth_bp.route('/mfa/setup', methods=['POST'])
@jwt_required
def mfa_setup():
    user   = g.current_user
    secret = generate_mfa_secret()
    uri    = get_totp_uri(secret, user['username'])
    qr     = generate_qr_base64(uri)
    return jsonify({'secret': secret, 'qr_code': qr}), 200


@auth_bp.route('/mfa/verify', methods=['POST'])
@jwt_required
def mfa_verify():
    data   = request.get_json(silent=True) or {}
    secret = data.get('secret', '').strip()
    code   = data.get('code', '').strip()
    if not secret or not code:
        return jsonify({'error': 'Secret and code are required'}), 422
    if not verify_totp(secret, code):
        return jsonify({'error': 'Invalid OTP code.'}), 401
    set_mfa_secret(str(g.current_user['id']), secret)
    log_event('mfa_enabled', str(g.current_user['id']), _ip())
    return jsonify({'message': 'Two-factor authentication enabled successfully.'}), 200


@auth_bp.route('/mfa/disable', methods=['POST'])
@jwt_required
def mfa_disable():
    data = request.get_json(silent=True) or {}
    code = data.get('code', '').strip()
    user = g.current_user

    if not user.get('mfa_enabled'):
        return jsonify({'error': 'MFA is not enabled on this account'}), 400
    if not code:
        return jsonify({'error': 'OTP code required to disable MFA'}), 422
    if not verify_totp(user['mfa_secret'], code):
        return jsonify({'error': 'Invalid OTP code'}), 401

    disable_mfa(str(user['id']))
    log_event('mfa_disabled', str(user['id']), _ip())
    return jsonify({'message': 'Two-factor authentication has been disabled.'}), 200


# ── Active Sessions ────────────────────────────────────────────

@auth_bp.route('/sessions', methods=['GET'])
@jwt_required
def list_sessions():
    sessions = get_all_user_sessions(str(g.current_user['id']))
    result = []
    for s in sessions:
        result.append({
            'id':         str(s['id']),
            'ip':         s.get('ip', '—'),
            'user_agent': (s.get('user_agent') or '')[:80],
            'created_at': s['created_at'],
            'current':    s['token'] == g.session_token,
        })
    return jsonify({'sessions': result}), 200


@auth_bp.route('/sessions/<session_id>', methods=['DELETE'])
@jwt_required
def revoke_session(session_id):
    from database import get_db
    db = get_db()
    r = db.table('sessions').select('*').eq('id', str(session_id)).eq('user_id', str(g.current_user['id'])).execute()
    if not r.data:
        return jsonify({'error': 'Session not found'}), 404
    db.table('sessions').update({'is_valid': False}).eq('id', str(session_id)).execute()
    log_event('session_revoked', str(g.current_user['id']), _ip(), {'session_id': session_id})
    return jsonify({'message': 'Session revoked'}), 200


# ── Current User ──────────────────────────────────────────────

@auth_bp.route('/me', methods=['GET'])
@jwt_required
def me():
    return jsonify({'user': safe_user(g.current_user)}), 200
