import uuid, os, hmac as hmac_mod, hashlib, json
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g

from middleware.auth_middleware import jwt_required, email_verified_required
from middleware.validation import validate_bid_amount
from models.audit_model import log_event
from database import get_db

wallet_bp = Blueprint('wallet', __name__)

MAX_DEPOSIT_PAISE  = 10_000_000_00  # ₹1 crore
MAX_WITHDRAW_PAISE = 1_000_000_00   # ₹10 lakh


def _ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()


def _add_tx(user_id, tx_type, amount, note='', razorpay_payment_id=None, auction_id=None):
    row = {
        'id':         str(uuid.uuid4()),
        'user_id':    str(user_id),
        'type':       tx_type,
        'amount':     amount,
        'note':       note,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    if razorpay_payment_id:
        row['razorpay_payment_id'] = razorpay_payment_id
    if auction_id:
        row['auction_id'] = str(auction_id)
    get_db().table('transactions').insert(row).execute()


# ── Balance ───────────────────────────────────────────────────

@wallet_bp.route('/balance', methods=['GET'])
@jwt_required
def get_balance():
    user = g.current_user
    return jsonify({
        'balance_paise': user.get('wallet_balance', 0),
        'balance_inr':   user.get('wallet_balance', 0) / 100,
    }), 200


# ── Deposit ───────────────────────────────────────────────────

@wallet_bp.route('/deposit', methods=['POST'])
@jwt_required
@email_verified_required
def deposit():
    data = request.get_json(silent=True) or {}
    try:
        amount = validate_bid_amount(data.get('amount', 0))
    except ValueError as e:
        return jsonify({'error': str(e)}), 422

    if amount > MAX_DEPOSIT_PAISE:
        return jsonify({'error': 'Deposit exceeds maximum limit'}), 422

    db          = get_db()
    new_balance = g.current_user.get('wallet_balance', 0) + amount
    db.table('users').update({
        'wallet_balance': new_balance,
        'updated_at':     datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(g.current_user['id'])).execute()
    _add_tx(str(g.current_user['id']), 'deposit', amount, 'Manual deposit')
    log_event('wallet_deposit', str(g.current_user['id']), _ip(), {'amount': amount})

    return jsonify({
        'message':       'Deposit successful',
        'balance_paise': new_balance,
        'balance_inr':   new_balance / 100,
    }), 200


# ── Withdraw ──────────────────────────────────────────────────

@wallet_bp.route('/withdraw', methods=['POST'])
@jwt_required
@email_verified_required
def withdraw():
    data = request.get_json(silent=True) or {}
    try:
        amount = validate_bid_amount(data.get('amount', 0))
    except ValueError as e:
        return jsonify({'error': str(e)}), 422

    if amount > MAX_WITHDRAW_PAISE:
        return jsonify({'error': 'Withdrawal exceeds maximum limit'}), 422

    user = g.current_user
    if user.get('wallet_balance', 0) < amount:
        return jsonify({'error': 'Insufficient balance'}), 402

    db          = get_db()
    new_balance = user.get('wallet_balance', 0) - amount
    db.table('users').update({
        'wallet_balance': new_balance,
        'updated_at':     datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(user['id'])).execute()
    _add_tx(str(user['id']), 'withdraw', amount, 'Withdrawal request')
    log_event('wallet_withdraw', str(user['id']), _ip(), {'amount': amount})

    return jsonify({
        'message':       'Withdrawal successful',
        'balance_paise': new_balance,
        'balance_inr':   new_balance / 100,
    }), 200


# ── Transaction history ────────────────────────────────────────

@wallet_bp.route('/transactions', methods=['GET'])
@jwt_required
def transactions():
    limit = min(int(request.args.get('limit', 20)), 100)
    skip  = int(request.args.get('skip', 0))
    r = get_db().table('transactions').select('*') \
        .eq('user_id', str(g.current_user['id'])) \
        .order('created_at', desc=True) \
        .range(skip, skip + limit - 1) \
        .execute()
    txs = []
    for t in (r.data or []):
        txs.append({
            'id':         str(t['id']),
            'type':       t['type'],
            'amount':     t['amount'],
            'amount_inr': t['amount'] / 100,
            'note':       t.get('note', ''),
            'created_at': t['created_at'],
        })
    return jsonify({'transactions': txs}), 200


# ── Razorpay: create order ─────────────────────────────────────

@wallet_bp.route('/razorpay/order', methods=['POST'])
@jwt_required
@email_verified_required
def razorpay_create_order():
    data = request.get_json(silent=True) or {}
    try:
        amount = validate_bid_amount(data.get('amount', 0))
    except ValueError as e:
        return jsonify({'error': str(e)}), 422

    rzp_key    = os.getenv('RAZORPAY_KEY_ID', '').strip().strip('"').strip("'")
    rzp_secret = os.getenv('RAZORPAY_KEY_SECRET', '').strip().strip('"').strip("'")

    # ── Sandbox / no keys configured ──────────────────────────
    if not rzp_key or not rzp_secret:
        mock_order_id = 'order_sandbox_' + uuid.uuid4().hex[:16]
        return jsonify({
            'order_id': mock_order_id,
            'amount':   amount,
            'currency': 'INR',
            'key':      'rzp_test_sandbox',
            'sandbox':  True,
        }), 200

    # ── Real Razorpay order ────────────────────────────────────
    try:
        import urllib.request, base64

        # Razorpay receipt must be ≤ 40 characters
        uid_short = str(g.current_user['id']).replace('-', '')[:20]
        receipt   = f'flexy_{uid_short}'[:40]

        payload = json.dumps({
            'amount':          amount,          # paise
            'currency':        'INR',
            'receipt':         receipt,
            'payment_capture': 1,
        }).encode('utf-8')

        credentials = base64.b64encode(
            f'{rzp_key}:{rzp_secret}'.encode('utf-8')
        ).decode('utf-8')

        req = urllib.request.Request(
            'https://api.razorpay.com/v1/orders',
            data=payload,
            headers={
                'Content-Type':  'application/json',
                'Authorization': f'Basic {credentials}',
            },
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            order = json.loads(resp.read().decode('utf-8'))

        return jsonify({
            'order_id': order['id'],
            'amount':   amount,
            'currency': 'INR',
            'key':      rzp_key,
        }), 200

    except urllib.error.HTTPError as e:
        # Read Razorpay's error body so we can surface it clearly
        body = ''
        try:
            body = e.read().decode('utf-8')
        except Exception:
            pass
        print(f'[RAZORPAY] HTTPError {e.code}: {body}')
        return jsonify({'error': f'Razorpay error {e.code}: {body}'}), 502

    except Exception as e:
        print(f'[RAZORPAY] Unexpected error: {e}')
        return jsonify({'error': f'Payment gateway error: {str(e)}'}), 500


# ── Razorpay: verify + credit wallet ──────────────────────────

@wallet_bp.route('/razorpay/verify', methods=['POST'])
@jwt_required
@email_verified_required
def razorpay_verify():
    data = request.get_json(silent=True) or {}

    razorpay_order_id   = data.get('razorpay_order_id', '')
    razorpay_payment_id = data.get('razorpay_payment_id', '')
    razorpay_signature  = data.get('razorpay_signature', '')
    amount              = int(data.get('amount', 0))

    rzp_secret = os.getenv('RAZORPAY_KEY_SECRET', '').strip().strip('"').strip("'")

    # ── Sandbox mode ──────────────────────────────────────────
    if not rzp_secret or razorpay_order_id.startswith('order_sandbox_'):
        if amount <= 0:
            return jsonify({'error': 'Invalid amount'}), 400
        db          = get_db()
        new_balance = g.current_user.get('wallet_balance', 0) + amount
        db.table('users').update({
            'wallet_balance': new_balance,
            'updated_at':     datetime.now(timezone.utc).isoformat(),
        }).eq('id', str(g.current_user['id'])).execute()
        _add_tx(str(g.current_user['id']), 'deposit', amount, 'Razorpay sandbox deposit')
        log_event('wallet_deposit', str(g.current_user['id']), _ip(),
                  {'amount': amount, 'mode': 'sandbox'})
        return jsonify({
            'message':       'Wallet credited successfully',
            'balance_paise': new_balance,
            'balance_inr':   new_balance / 100,
        }), 200

    # ── Production — verify HMAC signature ────────────────────
    # FIX: was `hmac.new(...)` which shadowed the module import.
    # Correct call: hmac_mod.new(key, msg, digestmod)
    expected_sig = hmac_mod.new(
        rzp_secret.encode('utf-8'),
        f'{razorpay_order_id}|{razorpay_payment_id}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()

    if not hmac_mod.compare_digest(expected_sig, razorpay_signature):
        log_event('payment_tampered', str(g.current_user['id']), _ip(),
                  {'order_id': razorpay_order_id})
        return jsonify({'error': 'Payment verification failed'}), 400

    # ── Idempotency check ─────────────────────────────────────
    db  = get_db()
    dup = db.table('transactions').select('id') \
            .eq('razorpay_payment_id', razorpay_payment_id).execute()
    if dup.data:
        return jsonify({'error': 'Payment already processed'}), 400

    # ── Credit wallet ─────────────────────────────────────────
    new_balance = g.current_user.get('wallet_balance', 0) + amount
    db.table('users').update({
        'wallet_balance': new_balance,
        'updated_at':     datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(g.current_user['id'])).execute()
    _add_tx(str(g.current_user['id']), 'deposit', amount,
            f'Razorpay {razorpay_payment_id}',
            razorpay_payment_id=razorpay_payment_id)
    log_event('wallet_deposit', str(g.current_user['id']), _ip(),
              {'amount': amount, 'mode': 'razorpay'})

    return jsonify({
        'message':       'Wallet credited successfully',
        'balance_paise': new_balance,
        'balance_inr':   new_balance / 100,
    }), 200