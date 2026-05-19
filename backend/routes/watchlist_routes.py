from flask import Blueprint, request, jsonify, g
from middleware.auth_middleware import jwt_required
from models.watchlist_model import add_to_watchlist, remove_from_watchlist, get_watchlist, is_watching
from models.auction_model import get_auction, safe_auction

watchlist_bp = Blueprint('watchlist', __name__)


# ── GET /api/watchlist/  ──────────────────────────────────────────────────────
@watchlist_bp.route('/', methods=['GET'])
@jwt_required
def get_watchlist_route():
    items   = get_watchlist(str(g.current_user['id']))
    results = []
    for w in items:
        auction = get_auction(str(w['auction_id']))
        if auction:
            results.append(safe_auction(auction))
    return jsonify({'watchlist': results}), 200


# ── POST /api/watchlist/<auction_id>  ─────────────────────────────────────────
# Called by the heart-button toggleWatch() in dashboard.js
@watchlist_bp.route('/<auction_id>', methods=['POST'])
@jwt_required
def add_by_id(auction_id):
    auction_id = auction_id.strip()
    if not auction_id:
        return jsonify({'error': 'auction_id is required'}), 400
    added = add_to_watchlist(str(g.current_user['id']), auction_id)
    return jsonify({'message': 'Added to wishlist' if added else 'Already in wishlist', 'added': added}), 200


# ── DELETE /api/watchlist/<auction_id>  ──────────────────────────────────────
@watchlist_bp.route('/<auction_id>', methods=['DELETE'])
@jwt_required
def remove_by_id(auction_id):
    auction_id = auction_id.strip()
    removed = remove_from_watchlist(str(g.current_user['id']), auction_id)
    return jsonify({'message': 'Removed from wishlist', 'removed': removed}), 200


# ── GET /api/watchlist/<auction_id>/status  ───────────────────────────────────
# Used by the auction detail fav-button to check current state
@watchlist_bp.route('/<auction_id>/status', methods=['GET'])
@jwt_required
def status_by_id(auction_id):
    watching = is_watching(str(g.current_user['id']), auction_id.strip())
    return jsonify({'watching': watching}), 200


# ── Legacy body-based endpoints (kept for backwards compat) ──────────────────
@watchlist_bp.route('/add', methods=['POST'])
@jwt_required
def add_watchlist():
    data       = request.get_json(silent=True) or {}
    auction_id = data.get('auction_id', '').strip()
    if not auction_id:
        return jsonify({'error': 'auction_id is required'}), 400
    added = add_to_watchlist(str(g.current_user['id']), auction_id)
    return jsonify({'message': 'Added to wishlist' if added else 'Already in wishlist', 'added': added}), 200


@watchlist_bp.route('/remove', methods=['POST'])
@jwt_required
def remove_watchlist():
    data       = request.get_json(silent=True) or {}
    auction_id = data.get('auction_id', '').strip()
    if not auction_id:
        return jsonify({'error': 'auction_id is required'}), 400
    removed = remove_from_watchlist(str(g.current_user['id']), auction_id)
    return jsonify({'message': 'Removed from wishlist', 'removed': removed}), 200


@watchlist_bp.route('/check/<auction_id>', methods=['GET'])
@jwt_required
def check_watchlist(auction_id):
    watching = is_watching(str(g.current_user['id']), auction_id)
    return jsonify({'watching': watching}), 200