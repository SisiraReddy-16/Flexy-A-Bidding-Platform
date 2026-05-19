"""
Flexy – Server-side input validation helpers.
All validation happens on the backend – never trust the client.
"""

import re
from typing import Any


EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
USERNAME_RE = re.compile(r'^[a-zA-Z0-9_]{3,30}$')


def validate_email(email: Any) -> str:
    if not isinstance(email, str):
        raise ValueError('Email must be a string')
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError('Invalid email address')
    return email


def validate_password(password: Any) -> str:
    if not isinstance(password, str):
        raise ValueError('Password must be a string')
    if len(password) < 8:
        raise ValueError('Password must be at least 8 characters')
    if len(password) > 128:
        raise ValueError('Password too long')
    if not re.search(r'[A-Z]', password):
        raise ValueError('Password must contain at least one uppercase letter')
    if not re.search(r'[a-z]', password):
        raise ValueError('Password must contain at least one lowercase letter')
    if not re.search(r'\d', password):
        raise ValueError('Password must contain at least one digit')
    return password


def validate_username(username: Any) -> str:
    if not isinstance(username, str):
        raise ValueError('Username must be a string')
    username = username.strip()
    if not USERNAME_RE.match(username):
        raise ValueError('Username must be 3–30 alphanumeric characters or underscores')
    return username


def validate_bid_amount(amount: Any) -> int:
    """Amount is expected in paise (int) or rupees (float/int)."""
    try:
        val = int(float(amount))
    except (TypeError, ValueError):
        raise ValueError('Invalid bid amount')
    if val <= 0:
        raise ValueError('Bid amount must be positive')
    if val > 100_000_000_00:   # ₹100 crore ceiling
        raise ValueError('Bid amount exceeds maximum allowed')
    return val


def sanitise_string(s: Any, max_len: int = 1000) -> str:
    if not isinstance(s, str):
        raise ValueError('Expected a string')
    s = s.strip()
    if len(s) > max_len:
        raise ValueError(f'Text exceeds {max_len} characters')
    # Basic injection guard – strip obvious script tags
    s = re.sub(r'<script.*?>.*?</script>', '', s, flags=re.IGNORECASE | re.DOTALL)
    return s
