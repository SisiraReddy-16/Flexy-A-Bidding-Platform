"""
Flexy – IP & user-level rate limiting using Flask-Limiter.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter: Limiter = None


def init_limiter(app):
    global limiter
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=['300 per minute', '2000 per hour'],
        storage_uri='memory://',
        headers_enabled=True,
    )
    return limiter


def get_limiter() -> Limiter:
    if limiter is None:
        raise RuntimeError('Limiter not initialised. Call init_limiter(app) first.')
    return limiter
