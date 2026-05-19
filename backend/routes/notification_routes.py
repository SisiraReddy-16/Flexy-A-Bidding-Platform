from flask import Blueprint, request, jsonify, g
from middleware.auth_middleware import jwt_required
from models.notification_model import (
    get_notifications, mark_read, mark_all_read, unread_count, safe_notif
)

notif_bp = Blueprint('notifications', __name__)


@notif_bp.route('/', methods=['GET'])
@jwt_required
def list_notifications():
    limit       = min(int(request.args.get('limit', 30)), 100)
    unread_only = request.args.get('unread', '').lower() == 'true'
    notifs      = get_notifications(str(g.current_user['id']), limit=limit, unread_only=unread_only)
    count       = unread_count(str(g.current_user['id']))
    return jsonify({
        'notifications': [safe_notif(n) for n in notifs],
        'unread_count':  count,
    }), 200


@notif_bp.route('/<notif_id>/read', methods=['POST'])
@jwt_required
def mark_notification_read(notif_id):
    mark_read(str(notif_id))
    return jsonify({'message': 'Marked as read'}), 200


@notif_bp.route('/read-all', methods=['POST'])
@jwt_required
def mark_all_notifications_read():
    mark_all_read(str(g.current_user['id']))
    return jsonify({'message': 'All notifications marked as read'}), 200


# ── /count and /unread both return the same thing ─────────────
# nav.js polls /unread every 30 s; keeping /count for backwards compat

@notif_bp.route('/count', methods=['GET'])
@notif_bp.route('/unread', methods=['GET'])
@jwt_required
def notification_count():
    count = unread_count(str(g.current_user['id']))
    return jsonify({'count': count, 'unread_count': count}), 200