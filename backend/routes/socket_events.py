import uuid
import threading
import time
from datetime import datetime, timezone

from flask import request
from flask_socketio import join_room, leave_room, emit

from models.session_model import get_session
from models.user_model import find_user_by_id
from models.auction_model import get_auction, place_bid, end_auction, safe_auction
from models.notification_model import create_notification
from models.audit_model import log_event
from services.email_service import send_auction_won_email
from database import get_db

_viewer_counts: dict[str, set] = {}
_viewer_lock   = threading.Lock()
_timers:        dict[str, threading.Thread] = {}
_timer_lock    = threading.Lock()


def _get_user():
    token = request.cookies.get('flexy_session') or request.args.get('token')
    if not token:
        return None
    session = get_session(token)
    if not session:
        return None
    return find_user_by_id(str(session['user_id']))


def _room(auction_id: str) -> str:
    return f'auction:{auction_id}'


def _parse_dt(s: str) -> datetime:
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _notify_user(sio, user_id: str, notif_type: str, title: str, body: str, meta: dict = None):
    n = create_notification(user_id, notif_type, title, body, meta or {})
    sio.emit('notification', {
        'id':    str(n['id']),
        'type':  notif_type,
        'title': title,
        'body':  body,
        'meta':  meta or {},
    }, room=f'user:{user_id}')


def register_socket_events(sio):

    @sio.on('connect')
    def on_connect():
        user = _get_user()
        # Allow anonymous connections (for viewing live bid updates)
        # Only authenticated users get a personal notification room
        if user is not None:
            join_room(f"user:{str(user['id'])}")

    @sio.on('disconnect')
    def on_disconnect():
        with _viewer_lock:
            for auction_id, viewers in list(_viewer_counts.items()):
                if request.sid in viewers:
                    viewers.discard(request.sid)
                    sio.emit('viewer_count', {
                        'auction_id': auction_id,
                        'count':      len(viewers),
                    }, room=_room(auction_id))

    @sio.on('join_auction')
    def on_join(data):
        auction_id = str(data.get('auction_id', ''))
        auction    = get_auction(auction_id)
        if not auction:
            emit('error', {'message': 'Auction not found'})
            return

        join_room(_room(auction_id))

        with _viewer_lock:
            _viewer_counts.setdefault(auction_id, set()).add(request.sid)
            count = len(_viewer_counts[auction_id])

        # Track view
        try:
            db = get_db()
            db.table('auctions').update({'view_count': auction.get('view_count', 0) + 1}).eq('id', str(auction_id)).execute()
        except Exception:
            pass

        # Auto-end if expired
        ends_at = _parse_dt(auction['ends_at'])
        if auction['status'] == 'active' and datetime.now(timezone.utc) > ends_at:
            _close_auction(sio, auction_id, auction)
            auction['status'] = 'ended'

        emit('auction_state', {'auction': safe_auction(auction), 'viewer_count': count})
        sio.emit('viewer_count', {'auction_id': auction_id, 'count': count}, room=_room(auction_id))

        # Send recent bid history
        db   = get_db()
        bids = db.table('bids').select('*').eq('auction_id', str(auction_id)).order('created_at', desc=True).limit(15).execute()
        history = []
        for b in (bids.data or []):
            bidder = find_user_by_id(str(b['bidder_id']))
            history.append({
                'bidder':     bidder['username'] if bidder else 'Unknown',
                'amount':     b['amount'],
                'created_at': b['created_at'],
            })
        emit('bid_history', {'bids': history})

        _ensure_timer(sio, auction_id)

    @sio.on('leave_auction')
    def on_leave(data):
        auction_id = str(data.get('auction_id', ''))
        leave_room(_room(auction_id))
        with _viewer_lock:
            if auction_id in _viewer_counts:
                _viewer_counts[auction_id].discard(request.sid)
                count = len(_viewer_counts[auction_id])
                sio.emit('viewer_count', {'auction_id': auction_id, 'count': count}, room=_room(auction_id))

    @sio.on('place_bid')
    def on_place_bid(data):
        user = _get_user()
        if not user:
            emit('bid_error', {'message': 'Authentication required'})
            return
        if not user.get('is_email_verified'):
            emit('bid_error', {'message': 'Please verify your email to bid'})
            return

        auction_id = str(data.get('auction_id', ''))
        try:
            amount_inr   = float(data.get('amount_inr', 0))
            amount_paise = int(round(amount_inr * 100))
        except (TypeError, ValueError):
            emit('bid_error', {'message': 'Invalid amount'})
            return

        if amount_paise <= 0:
            emit('bid_error', {'message': 'Bid must be positive'})
            return

        auction = get_auction(auction_id)
        if not auction:
            emit('bid_error', {'message': 'Auction not found'})
            return
        if str(auction['created_by']) == str(user['id']):
            emit('bid_error', {'message': 'You cannot bid on your own auction'})
            return

        ends_at = _parse_dt(auction['ends_at'])
        if datetime.now(timezone.utc) > ends_at:
            emit('bid_error', {'message': 'Auction has ended'})
            return

        if user.get('wallet_balance', 0) < amount_paise:
            emit('bid_error', {'message': 'Insufficient wallet balance'})
            return

        prev_bidder_id = auction.get('current_bidder')

        try:
            bid = place_bid(auction_id, str(user['id']), amount_paise)
        except ValueError as e:
            emit('bid_error', {'message': str(e)})
            return

        # Deduct wallet + record transaction
        db = get_db()
        new_balance = user.get('wallet_balance', 0) - amount_paise
        db.table('users').update({'wallet_balance': new_balance}).eq('id', str(user['id'])).execute()
        db.table('transactions').insert({
            'id':         str(uuid.uuid4()),
            'user_id':    str(user['id']),
            'type':       'bid',
            'amount':     amount_paise,
            'note':       f"Bid on: {auction['title']}",
            'auction_id': str(auction_id),
            'created_at': bid['created_at'],
        }).execute()

        log_event('bid_placed', str(user['id']), request.remote_addr or '127.0.0.1', {
            'auction_id': auction_id, 'amount': amount_paise,
        })

        # Notify previous highest bidder
        if prev_bidder_id and str(prev_bidder_id) != str(user['id']):
            _notify_user(sio, str(prev_bidder_id), 'outbid',
                "⚡ You've been outbid!",
                f'Someone bid ₹{amount_inr:,.0f} on "{auction["title"]}". Bid higher to reclaim the lead!',
                {'auction_id': auction_id})

        new_count = auction.get('bid_count', 0) + 1
        sio.emit('bid_update', {
            'auction_id':      auction_id,
            'current_bid':     amount_paise,
            'current_bid_inr': f'₹{amount_inr:,.0f}',
            'bid_count':       new_count,
            'bidder':          user['username'],
            'timestamp':       bid['created_at'],
        }, room=_room(auction_id))

        # Confirm to bidder
        refreshed = find_user_by_id(str(user['id']))
        emit('bid_success', {
            'message':     'Bid placed!',
            'amount':      amount_paise,
            'new_balance': refreshed.get('wallet_balance', 0) if refreshed else 0,
        })


# ── Timer helpers ─────────────────────────────────────────────

def _ensure_timer(sio, auction_id: str):
    with _timer_lock:
        if auction_id in _timers and _timers[auction_id].is_alive():
            return
    t = threading.Thread(target=_run_countdown, args=(sio, auction_id), daemon=True)
    with _timer_lock:
        _timers[auction_id] = t
    t.start()


def _run_countdown(sio, auction_id: str):
    warned_5min = False
    while True:
        auction = get_auction(auction_id)
        if not auction or auction.get('status') != 'active':
            break

        ends_at      = _parse_dt(auction['ends_at'])
        seconds_left = (ends_at - datetime.now(timezone.utc)).total_seconds()

        if seconds_left <= 0:
            _close_auction(sio, auction_id, auction)
            break

        if not warned_5min and seconds_left <= 300:
            warned_5min = True
            _send_ending_soon_notifications(sio, auction_id, auction)

        sio.emit('timer_update', {
            'auction_id':   auction_id,
            'seconds_left': int(seconds_left),
        }, room=_room(auction_id))

        time.sleep(1)

    with _timer_lock:
        _timers.pop(auction_id, None)


def _close_auction(sio, auction_id: str, auction: dict):
    end_auction(auction_id)
    refreshed = get_auction(auction_id)

    winner_id       = refreshed.get('current_bidder') if refreshed else None
    winner_username = None
    final_bid       = refreshed.get('current_bid', 0) if refreshed else 0
    title           = auction.get('title', 'Auction')
    order_id        = None

    if winner_id:
        winner = find_user_by_id(str(winner_id))
        if winner:
            winner_username = winner['username']
            from models.order_model import create_order
            order    = create_order(str(winner_id), auction_id, final_bid)
            order_id = str(order['id'])
            try:
                auction_title = refreshed.get('title', 'Your Auction Item') if refreshed else 'Your Auction Item'
                send_auction_won_email(winner['email'], winner['username'], auction_title, final_bid, order_id)
            except Exception as e:
                print(f'[MAIL] Could not send winner email: {e}')

            _notify_user(sio, str(winner_id), 'auction_won',
                '🏆 You won the auction!',
                f'Congratulations! You won "{title}" with a bid of ₹{final_bid/100:,.0f}!',
                {'auction_id': auction_id, 'final_bid': final_bid, 'order_id': order_id, 'action_url': f'/order/{order_id}'})

    sio.emit('auction_ended', {
        'auction_id':    auction_id,
        'winner':        winner_username or 'No winner',
        'final_bid':     final_bid,
        'final_bid_inr': f'₹{final_bid/100:,.0f}',
        'order_id':      order_id,
    }, room=_room(auction_id))


def _send_ending_soon_notifications(sio, auction_id: str, auction: dict):
    db    = get_db()
    title = auction.get('title', 'Auction')
    # Notify all watchers
    w_r = db.table('watchlist').select('user_id').eq('auction_id', str(auction_id)).execute()
    for w in (w_r.data or []):
        _notify_user(sio, str(w['user_id']), 'auction_ending_soon',
            '⏰ Auction ending soon!',
            f'"{title}" ends in under 5 minutes. Place your final bid now!',
            {'auction_id': auction_id})
