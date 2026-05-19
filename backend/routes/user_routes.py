import re, uuid
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g

from middleware.auth_middleware import jwt_required
from middleware.validation import sanitise_string
from models.user_model import safe_user
from models.audit_model import get_recent_events
from models.auction_model import safe_auction
from database import get_db

user_bp = Blueprint('user', __name__)


# ── Profile ───────────────────────────────────────────────────

@user_bp.route('/profile', methods=['GET'])
@jwt_required
def get_profile():
    return jsonify({'user': safe_user(g.current_user)}), 200


@user_bp.route('/profile', methods=['PUT'])
@jwt_required
def update_profile():
    data    = request.get_json(silent=True) or {}
    updates = {}

    for field, max_len in [('bio', 300), ('avatar_url', 500), ('location', 100)]:
        if field in data:
            try:
                updates[field] = sanitise_string(data[field], max_len=max_len)
            except ValueError as e:
                return jsonify({'error': str(e)}), 422

    if not updates:
        return jsonify({'error': 'Nothing to update'}), 422

    updates['updated_at'] = datetime.now(timezone.utc).isoformat()
    db = get_db()
    db.table('users').update(updates).eq('id', str(g.current_user['id'])).execute()
    refreshed = db.table('users').select('*').eq('id', str(g.current_user['id'])).execute()
    return jsonify({'message': 'Profile updated', 'user': safe_user(refreshed.data[0])}), 200


# ── Stats ─────────────────────────────────────────────────────

@user_bp.route('/stats', methods=['GET'])
@jwt_required
def user_stats():
    db      = get_db()
    user_id = str(g.current_user['id'])

    won_r          = db.table('auctions').select('id,current_bid').eq('status', 'ended').eq('current_bidder', user_id).execute()
    items_won      = won_r.data or []
    items_won_count= len(items_won)

    bids_r       = db.table('bids').select('auction_id').eq('bidder_id', user_id).execute()
    auction_ids  = list({b['auction_id'] for b in (bids_r.data or [])})
    active_bids  = 0
    for aid in auction_ids:
        a_r = db.table('auctions').select('id').eq('id', aid).eq('status', 'active').execute()
        if a_r.data:
            active_bids += 1

    won_value      = sum(a.get('current_bid', 0) for a in items_won)
    total_val      = g.current_user.get('wallet_balance', 0) + won_value

    return jsonify({
        'items_won':           items_won_count,
        'active_bids':         active_bids,
        'total_valuation_inr': total_val / 100,
    }), 200


# ── Audit log ─────────────────────────────────────────────────

@user_bp.route('/audit-log', methods=['GET'])
@jwt_required
def audit_log():
    events = get_recent_events(str(g.current_user['id']))
    result = [{
        'event_type': e['event_type'],
        'ip':         e.get('ip', ''),
        'meta':       e.get('meta', {}),
        'created_at': e['created_at'],
    } for e in events]
    return jsonify({'events': result}), 200


# ── My auctions ────────────────────────────────────────────────

@user_bp.route('/my-auctions', methods=['GET'])
@jwt_required
def my_auctions():
    limit = min(int(request.args.get('limit', 20)), 50)
    skip  = int(request.args.get('skip', 0))
    r     = get_db().table('auctions').select('*').eq('created_by', str(g.current_user['id'])).order('created_at', desc=True).range(skip, skip + limit - 1).execute()
    return jsonify({'auctions': [safe_auction(a) for a in (r.data or [])]}), 200


# ── My bids ────────────────────────────────────────────────────

@user_bp.route('/my-bids', methods=['GET'])
@jwt_required
def my_bids():
    limit = min(int(request.args.get('limit', 20)), 50)
    skip  = int(request.args.get('skip', 0))
    db    = get_db()
    bids_r = db.table('bids').select('*').eq('bidder_id', str(g.current_user['id'])).order('created_at', desc=True).range(skip, skip + limit - 1).execute()
    bids   = []
    for b in (bids_r.data or []):
        a_r = db.table('auctions').select('id,title').eq('id', str(b['auction_id'])).execute()
        title = a_r.data[0]['title'] if a_r.data else 'Unknown'
        bids.append({
            'id':            str(b['id']),
            'amount':        b['amount'],
            'amount_inr':    b['amount'] / 100,
            'auction_id':    str(b['auction_id']),
            'auction_title': title,
            'created_at':    b['created_at'],
        })
    return jsonify({'bids': bids}), 200


# ── Seller KYC ─────────────────────────────────────────────────

@user_bp.route('/kyc', methods=['POST'])
@jwt_required
def submit_kyc():
    data          = request.get_json(silent=True) or {}
    legal_name    = (data.get('legal_name') or '').strip()
    pan           = (data.get('pan') or '').strip().upper()
    aadhaar_last4 = (data.get('aadhaar_last4') or '').strip()
    bank_account  = (data.get('bank_account') or '').strip()
    bank_ifsc     = (data.get('bank_ifsc') or '').strip().upper()

    if not legal_name:
        return jsonify({'error': 'Legal name is required'}), 422
    if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', pan):
        return jsonify({'error': 'Invalid PAN format (e.g. ABCDE1234F)'}), 422
    if not re.match(r'^[0-9]{4}$', aadhaar_last4):
        return jsonify({'error': 'Enter last 4 digits of Aadhaar'}), 422

    get_db().table('users').update({
        'kyc_status':         'approved',
        'is_seller_verified': True,
        'kyc_legal_name':     legal_name,
        'kyc_pan':            pan,
        'kyc_aadhaar_last4':  aadhaar_last4,
        'kyc_bank_account':   bank_account,
        'kyc_bank_ifsc':      bank_ifsc,
        'kyc_submitted_at':   datetime.now(timezone.utc).isoformat(),
        'updated_at':         datetime.now(timezone.utc).isoformat(),
    }).eq('id', str(g.current_user['id'])).execute()

    return jsonify({'message': 'KYC approved. You can now list items for auction.'}), 200


@user_bp.route('/kyc', methods=['GET'])
@jwt_required
def get_kyc_status():
    user = g.current_user
    return jsonify({
        'kyc_status':         user.get('kyc_status', 'not_submitted'),
        'is_seller_verified': user.get('is_seller_verified', False),
    }), 200
