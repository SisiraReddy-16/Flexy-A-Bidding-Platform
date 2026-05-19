"""
Flexy – Authentication & authorisation middleware.
Uses HttpOnly cookies (token) + CSRF header check.
"""

import os
from functools import wraps

from flask import request, jsonify, g, current_app

from models.session_model import get_session
from models.user_model import find_user_by_id


def _get_token_from_request() -> str | None:
    # 1. HttpOnly cookie (primary)
    token = request.cookies.get('flexy_session')
    if token:
        return token
    # 2. Authorization header (API clients / testing)
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return None


def jwt_required(f):
    """Decorator: require a valid session cookie."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _get_token_from_request()
        if not token:
            return jsonify({'error': 'Authentication required'}), 401

        session = get_session(token)
        if not session:
            return jsonify({'error': 'Session expired or invalid'}), 401

        user = find_user_by_id(str(session['user_id']))
        if not user:
            return jsonify({'error': 'User not found'}), 401
        if user.get('is_locked'):
            return jsonify({'error': 'Account is locked. Contact support.'}), 403

        # Attach to request context
        g.current_user = user
        g.session_token = token
        return f(*args, **kwargs)
    return decorated


def roles_required(*roles):
    """Decorator: require specific role(s). Must be used after @jwt_required."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = getattr(g, 'current_user', None)
            if not user or user.get('role') not in roles:
                return jsonify({'error': 'Forbidden'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def email_verified_required(f):
    """Decorator: require verified email. Must be used after @jwt_required."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = getattr(g, 'current_user', None)
        if not user or not user.get('is_email_verified'):
            return jsonify({'error': 'Email verification required'}), 403
        return f(*args, **kwargs)
    return decorated
