"""
Flexy – Multi-Factor Authentication service.
Uses pyotp for TOTP (Google Authenticator compatible).
"""

import pyotp
import qrcode
import io
import base64


def generate_mfa_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str, issuer: str = 'Flexy') -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=username,
        issuer_name=issuer,
    )


def generate_qr_base64(uri: str) -> str:
    """Return a base64-encoded PNG of the QR code."""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
