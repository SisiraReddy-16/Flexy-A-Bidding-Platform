import os
import json
import threading
import urllib.request
import urllib.error


# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

def _get_config():
    api_key      = os.environ.get('BREVO_API_KEY', '')
    sender_email = os.environ.get('MAIL_USERNAME', '')
    sender_name  = os.environ.get('MAIL_FROM_NAME', 'Flexy')
    return api_key, sender_email, sender_name


def _configured():
    api_key, sender_email, _ = _get_config()
    ok = bool(api_key and sender_email)
    if not ok:
        print('[MAIL ERROR] BREVO_API_KEY or MAIL_USERNAME env var is not set!', flush=True)
    return ok


# ─────────────────────────────────────────────────────────────
# CORE SEND
# ─────────────────────────────────────────────────────────────

def _print_terminal(to, subject, body_text):
    sep = '=' * 62
    print(f'\n{sep}', flush=True)
    print(f'  FLEXY MAIL  →  {to}', flush=True)
    print(f'  Subject: {subject}', flush=True)
    print(f'  {body_text}', flush=True)
    print(f'{sep}\n', flush=True)


def _send_via_brevo(to: str, subject: str, html: str):
    api_key, sender_email, sender_name = _get_config()

    payload = json.dumps({
        'sender':      {'name': sender_name, 'email': sender_email},
        'to':          [{'email': to}],
        'subject':     subject,
        'htmlContent': html,
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.brevo.com/v3/smtp/email',
        data=payload,
        headers={
            'api-key':      api_key,
            'Content-Type': 'application/json',
            'Accept':       'application/json',
        },
        method='POST',
    )

    print(f'[MAIL DEBUG] Sending via Brevo API to {to} ...', flush=True)
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode()
        print(f'[MAIL SUCCESS] Brevo accepted → {body}', flush=True)


def _send_in_background(to: str, subject: str, html: str, plain_summary: str):
    _print_terminal(to, subject, plain_summary)
    if not _configured():
        return
    try:
        _send_via_brevo(to, subject, html)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f'[MAIL ERROR] Brevo HTTP {e.code}: {body}', flush=True)
    except Exception as e:
        print(f'[MAIL ERROR] {type(e).__name__}: {e}', flush=True)


def _send(to: str, subject: str, html: str, plain_summary: str):
    t = threading.Thread(
        target=_send_in_background,
        args=(to, subject, html, plain_summary),
        daemon=False,
    )
    t.start()


# ─────────────────────────────────────────────────────────────
# EMAIL TEMPLATES
# ─────────────────────────────────────────────────────────────

def send_verification_email(to: str, username: str, otp: str) -> None:
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"/></head>
    <body style="margin:0;padding:0;background:#0e0e0e;font-family:'Segoe UI',Arial,sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#0e0e0e;padding:2rem 0;">
    <tr><td align="center">
    <table width="520" cellpadding="0" cellspacing="0"
           style="background:#141414;border:1px solid #2a2a2a;border-radius:16px;overflow:hidden;max-width:520px;">
      <tr>
        <td style="background:linear-gradient(135deg,#44007f,#9c3dff);padding:2rem;text-align:center;">
          <h1 style="margin:0;font-size:2.25rem;font-weight:900;color:#fff;letter-spacing:-1px;">Flexy</h1>
          <p style="margin:.25rem 0 0;color:rgba(255,255,255,.7);font-size:.85rem;">High-Velocity Bidding Platform</p>
        </td>
      </tr>
      <tr>
        <td style="padding:2.5rem 2rem;">
          <h2 style="color:#fff;margin:0 0 .5rem;font-size:1.4rem;font-weight:700;">Welcome, {username}! 👋</h2>
          <p style="color:#999;margin:0 0 2rem;line-height:1.7;font-size:.95rem;">
            Use this OTP to verify your account. It expires in
            <strong style="color:#ff94a3;">10 minutes</strong>.
          </p>
          <div style="text-align:center;margin:0 0 2rem;">
            <div style="display:inline-block;background:#1a0035;border:2px solid #c899ff;border-radius:14px;padding:1.25rem 3rem;">
              <span style="font-size:2.75rem;font-weight:900;letter-spacing:.4em;color:#c899ff;font-family:'Courier New',monospace;">
                {otp}
              </span>
            </div>
            <p style="color:#666;font-size:.8rem;margin:.75rem 0 0;">Never share this OTP with anyone.</p>
          </div>
        </td>
      </tr>
      <tr>
        <td style="background:#0a0a0a;padding:1rem 2rem;text-align:center;border-top:1px solid #1e1e1e;">
          <p style="color:#444;font-size:.75rem;margin:0;">© 2026 Flexy · India's Premium Bidding Platform</p>
        </td>
      </tr>
    </table>
    </td></tr>
    </table>
    </body>
    </html>
    """
    _send(to, f"Flexy OTP: {otp}", html, f"Your OTP is: {otp} (expires in 10 minutes)")


# ─────────────────────────────────────────────────────────────
# PLACEHOLDER EMAILS
# ─────────────────────────────────────────────────────────────

def send_password_reset_email(to: str, username: str, token: str):
    print(f'[MAIL] Password reset email placeholder for {to}', flush=True)


def send_login_alert_email(to: str, username: str, ip: str, user_agent: str):
    print(f'[MAIL] Login alert placeholder for {to}', flush=True)


def send_auction_won_email(to: str, username: str, auction_title: str, amount: int, order_id: str):
    print(f'[MAIL] Auction won email placeholder for {to}', flush=True)