from flask import Blueprint, jsonify, request, g
from middleware.auth_middleware import jwt_required
from models.auction_model import get_auction, safe_auction
from models.order_model import create_order, get_order, update_order_status, safe_order, get_user_orders
from models.audit_model import log_event
from database import get_db

order_bp = Blueprint('order', __name__)


def _ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()


@order_bp.route('/', methods=['GET'])
@jwt_required
def list_orders():
    orders = get_user_orders(str(g.current_user['id']))
    result = []
    for o in orders:
        auction = get_auction(str(o['auction_id']))
        result.append({
            **safe_order(o),
            'auction': safe_auction(auction) if auction else None,
        })
    return jsonify({'orders': result}), 200


@order_bp.route('/<order_id>', methods=['GET'])
@jwt_required
def fetch_order(order_id):
    order = get_order(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    if str(order['user_id']) != str(g.current_user['id']):
        return jsonify({'error': 'Unauthorised'}), 403
    auction = get_auction(str(order['auction_id']))
    return jsonify({'order': safe_order(order), 'auction': safe_auction(auction) if auction else None}), 200


@order_bp.route('/<order_id>/pay', methods=['POST'])
@jwt_required
def pay_order(order_id):
    data    = request.get_json(silent=True) or {}
    method  = data.get('method', '').strip().lower()
    address = data.get('address', {})

    if method not in ('cod', 'razorpay', 'wallet'):
        return jsonify({'error': 'Invalid payment method. Use cod, razorpay, or wallet.'}), 400

    if not address or not address.get('full_name') or not address.get('city') or not address.get('pincode'):
        return jsonify({'error': 'Full name, city and pincode are required in address'}), 400

    order = get_order(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    if str(order['user_id']) != str(g.current_user['id']):
        return jsonify({'error': 'Unauthorised'}), 403
    if order['status'] != 'pending_payment':
        return jsonify({'error': 'Order has already been processed'}), 400

    if method == 'wallet':
        user = g.current_user
        if user.get('wallet_balance', 0) < order['amount']:
            return jsonify({'error': 'Insufficient wallet balance'}), 402
        db = get_db()
        from datetime import datetime, timezone
        import uuid
        new_bal = user.get('wallet_balance', 0) - order['amount']
        db.table('users').update({
            'wallet_balance': new_bal,
            'updated_at':     datetime.now(timezone.utc).isoformat(),
        }).eq('id', str(user['id'])).execute()
        db.table('transactions').insert({
            'id':         str(uuid.uuid4()),
            'user_id':    str(user['id']),
            'type':       'order_payment',
            'amount':     order['amount'],
            'note':       f'Payment for order {order_id}',
            'auction_id': str(order['auction_id']),
            'created_at': datetime.now(timezone.utc).isoformat(),
        }).execute()

    new_status = 'cod' if method == 'cod' else 'paid'
    update_order_status(order_id, new_status, method, address)
    log_event('order_completed', str(g.current_user['id']), _ip(), {'order_id': order_id, 'method': method})
    return jsonify({'message': 'Order successfully placed!', 'status': new_status}), 200
