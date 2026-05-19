from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, g
from middleware.auth_middleware import jwt_required, email_verified_required
from middleware.validation import sanitise_string, validate_bid_amount
from models.auction_model import (
    create_auction, get_auction, list_auctions,
    place_bid, get_bid_history, safe_auction, end_auction,
)
from models.user_model import find_user_by_id
from models.watchlist_model import is_watching
from models.audit_model import log_event
from database import get_db
import uuid

auction_bp = Blueprint('auctions', __name__)

def _ip(): return request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()

def _parse_dt(s):
    if not s: return None
    if s.endswith('Z'): s = s[:-1]+'+00:00'
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def _auto_status(auction):
    """Recalculate status: upcoming→active when start time passed, active→ended when end time passed."""
    now = datetime.now(timezone.utc)
    status = auction.get('status', 'active')
    ends_at = _parse_dt(auction.get('ends_at'))
    starts_at = _parse_dt(auction.get('starts_at'))

    if status == 'ended':
        return 'ended'
    if status == 'upcoming' and starts_at and now >= starts_at:
        # Transition to active
        get_db().table('auctions').update({'status': 'active'}).eq('id', str(auction['id'])).execute()
        return 'active'
    if status == 'active' and ends_at and now > ends_at:
        end_auction(str(auction['id']))
        return 'ended'
    return status

# ── List ──────────────────────────────────────────────────────
@auction_bp.route('/', methods=['GET'])
def list_auctions_route():
    status   = request.args.get('status', 'active')
    category = request.args.get('category')
    sort     = request.args.get('sort', 'ends_at')
    limit    = min(int(request.args.get('limit', 20)), 50)
    skip     = int(request.args.get('skip', 0))
    search   = request.args.get('q', '').strip()

    db = get_db()
    q  = db.table('auctions').select('*').eq('status', status)
    if category and category != 'all':
        q = q.eq('category', category)
    if search:
        q = q.ilike('title', f'%{search}%')

    col, desc = {'ends_at':('ends_at',False),'bid_high':('current_bid',True),
                 'newest':('created_at',True),'popular':('bid_count',True)}.get(sort, ('ends_at',False))
    auctions = q.order(col, desc=desc).range(skip, skip+limit-1).execute().data or []
    return jsonify({'auctions': [safe_auction(a) for a in auctions], 'count': len(auctions)}), 200

# ── Homepage sections ─────────────────────────────────────────
@auction_bp.route('/sections', methods=['GET'])
def homepage_sections():
    db = get_db()

    # Sweep: auto-end any active auctions whose end time has passed
    try:
        now = datetime.now(timezone.utc)
        stale = db.table('auctions').select('id,ends_at').eq('status', 'active').execute().data or []
        for a in stale:
            ends = _parse_dt(a.get('ends_at', '')) if a.get('ends_at') else None
            if ends and now > ends:
                end_auction(str(a['id']))
        # Sweep: auto-activate any upcoming auctions whose start time has passed
        upcoming = db.table('auctions').select('id,starts_at').eq('status', 'upcoming').execute().data or []
        for a in upcoming:
            starts = _parse_dt(a.get('starts_at', '')) if a.get('starts_at') else None
            if starts and now >= starts:
                db.table('auctions').update({'status': 'active'}).eq('id', str(a['id'])).execute()
    except Exception:
        pass

    def _q(status, sort_col, desc, lim=8):
        return [safe_auction(a) for a in (db.table('auctions').select('*').eq('status', status)
                .order(sort_col, desc=desc).limit(lim).execute().data or [])]

    live     = _q('active',   'ends_at',   False)
    upcoming = _q('upcoming', 'ends_at',   False)
    ended    = _q('ended',    'created_at',True, 4)
    popular  = _q('active',   'bid_count', True)
    feat_r   = db.table('auctions').select('*').eq('status','active').eq('is_featured',True).order('ends_at').limit(6).execute()
    return jsonify({
        'live_now':    live,
        'upcoming':    upcoming,
        'ended':       ended,
        'popular':     popular,
        'featured':    [safe_auction(a) for a in (feat_r.data or [])],
    }), 200

# ── Categories ────────────────────────────────────────────────
@auction_bp.route('/categories', methods=['GET'])
def list_categories():
    r = get_db().table('auctions').select('category').neq('status','ended').execute()
    cats = {}
    for row in (r.data or []):
        c = row.get('category') or 'Other'
        cats[c] = cats.get(c,0)+1
    return jsonify({'categories': [{'name':k,'count':v} for k,v in sorted(cats.items(),key=lambda x:-x[1])]}), 200

# ── Create ────────────────────────────────────────────────────
@auction_bp.route('/', methods=['POST'])
@jwt_required
@email_verified_required
def create_auction_route():
    data = request.get_json(silent=True) or {}
    user = g.current_user
    if not user.get('is_seller_verified'):
        return jsonify({'error': 'Seller KYC required. Complete verification in Settings.'}), 403
    try:
        title          = sanitise_string(data.get('title',''), max_len=120)
        description    = sanitise_string(data.get('description',''), max_len=2000)
        category       = sanitise_string(data.get('category','Other'), max_len=50)
        image_url      = sanitise_string(data.get('image_url',''), max_len=500)
        starting_price = validate_bid_amount(data.get('starting_price',0))
        reserve_price  = validate_bid_amount(data.get('reserve_price',0)) if data.get('reserve_price') else 0
        duration_hours = int(data.get('duration_hours',24))
        if not (1 <= duration_hours <= 168): raise ValueError('Duration must be 1–168 hours')
    except (ValueError, TypeError) as e:
        return jsonify({'error': str(e)}), 422
    if not title: return jsonify({'error': 'Title is required'}), 422

    ends_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
    auction = create_auction({'title':title,'description':description,'category':category,
        'image_url':image_url,'starting_price':starting_price,'reserve_price':reserve_price,
        'ends_at':ends_at,'tags':data.get('tags',[])}, str(user['id']))
    log_event('auction_created', str(user['id']), _ip(), {'auction_id': str(auction['id'])})
    return jsonify({'auction': safe_auction(auction), 'message': 'Auction created'}), 201

# ── Get single ────────────────────────────────────────────────
@auction_bp.route('/<auction_id>', methods=['GET'])
def get_auction_route(auction_id):
    auction = get_auction(auction_id)
    if not auction: return jsonify({'error': 'Auction not found'}), 404

    # Auto-transition status
    real_status = _auto_status(auction)
    auction['status'] = real_status

    ends_at = _parse_dt(auction['ends_at'])
    result  = safe_auction(auction)
    result['seconds_left'] = max(0, int((ends_at - datetime.now(timezone.utc)).total_seconds())) \
        if real_status == 'active' and ends_at else 0

    seller = find_user_by_id(str(auction['created_by']))
    if seller:
        result['seller'] = {'username': seller['username'], 'avatar_url': seller.get('avatar_url','')}

    # Increment view
    try:
        get_db().table('auctions').update({'view_count': auction.get('view_count',0)+1}).eq('id', str(auction_id)).execute()
    except Exception: pass

    # Per-user data
    try:
        from middleware.auth_middleware import _get_token_from_request
        from models.session_model import get_session
        token = _get_token_from_request()
        if token:
            session = get_session(token)
            if session:
                uid = str(session['user_id'])
                result['is_watching'] = is_watching(uid, auction_id)
                # Check if this user is winner with pending order
                if real_status == 'ended' and str(auction.get('current_bidder','')) == uid:
                    db = get_db()
                    ord_r = db.table('orders').select('id,status').eq('auction_id', str(auction_id)).eq('user_id', uid).execute()
                    if ord_r.data:
                        result['order_id']     = str(ord_r.data[0]['id'])
                        result['order_status'] = ord_r.data[0].get('status')
    except Exception:
        result['is_watching'] = False

    return jsonify({'auction': result}), 200

# ── Place Bid (REST fallback) ─────────────────────────────────
@auction_bp.route('/<auction_id>/bid', methods=['POST'])
@jwt_required
@email_verified_required
def place_bid_route(auction_id):
    data = request.get_json(silent=True) or {}
    user = g.current_user

    # Accept amount in paise OR amount_inr
    try:
        if 'amount_inr' in data:
            amount_paise = int(round(float(data['amount_inr']) * 100))
        else:
            amount_paise = validate_bid_amount(data.get('amount', 0))
    except ValueError as e:
        return jsonify({'error': str(e)}), 422

    auction = get_auction(auction_id)
    if not auction: return jsonify({'error': 'Auction not found'}), 404

    real_status = _auto_status(auction)
    if real_status != 'active': return jsonify({'error': f'Auction is {real_status}, not accepting bids'}), 400
    if str(auction['created_by']) == str(user['id']): return jsonify({'error': 'Cannot bid on your own auction'}), 403
    if amount_paise <= auction['current_bid']: return jsonify({'error': f'Bid must exceed current bid of ₹{auction["current_bid"]//100:,}'}), 422
    if user.get('wallet_balance', 0) < amount_paise: return jsonify({'error': 'Insufficient wallet balance'}), 402

    try:
        bid = place_bid(auction_id, str(user['id']), amount_paise)
    except ValueError as e:
        return jsonify({'error': str(e)}), 422

    db = get_db()
    new_balance = user.get('wallet_balance', 0) - amount_paise
    db.table('users').update({'wallet_balance': new_balance}).eq('id', str(user['id'])).execute()
    db.table('transactions').insert({
        'id': str(uuid.uuid4()), 'user_id': str(user['id']),
        'type': 'bid', 'amount': amount_paise,
        'note': f"Bid on: {auction['title']}", 'auction_id': str(auction_id),
        'created_at': bid['created_at'],
    }).execute()

    log_event('bid_placed', str(user['id']), _ip(), {'auction_id': auction_id, 'amount': amount_paise})

    # Broadcast via SocketIO
    try:
        from app import socketio
        socketio.emit('bid_update', {
            'auction_id': auction_id, 'current_bid': amount_paise,
            'current_bid_inr': f'₹{amount_paise//100:,}',
            'bid_count': auction.get('bid_count',0)+1,
            'bidder': user['username'], 'timestamp': bid['created_at'],
        }, room=f'auction:{auction_id}')
    except Exception: pass

    return jsonify({'message': 'Bid placed successfully', 'bid': {
        'id': str(bid['id']), 'amount': bid['amount'],
        'amount_inr': bid['amount']/100, 'created_at': bid['created_at'],
    }, 'new_wallet_balance': new_balance}), 201

# ── Bid history ────────────────────────────────────────────────
@auction_bp.route('/<auction_id>/bids', methods=['GET'])
def bid_history_route(auction_id):
    limit = min(int(request.args.get('limit',20)), 50)
    bids  = get_bid_history(auction_id, limit=limit)
    result = []
    for b in bids:
        bidder = find_user_by_id(str(b['bidder_id']))
        result.append({
            'id': str(b['id']), 'amount': b['amount'],
            'amount_inr': b['amount']/100,
            'bidder': bidder['username'] if bidder else 'Unknown',
            'created_at': b['created_at'],
        })
    return jsonify({'bids': result}), 200
