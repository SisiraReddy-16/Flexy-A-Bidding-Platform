import os
from flask import Flask, render_template, request, make_response, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
from dotenv import load_dotenv
import pathlib

_env_path = pathlib.Path(__file__).parent / '.env'
# IMPORTANT: override=False means real environment variables (set by Render/Heroku/etc.)
# take priority over the .env file. This is correct for production deployments.
# The .env file is only used for local dev when the vars aren't already set.
load_dotenv(dotenv_path=_env_path, override=False)

socketio = SocketIO()


def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'static'),
        template_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend', 'templates'),
    )

    app.config.update({
        'SECRET_KEY':              os.getenv('SECRET_KEY', 'dev-secret-change-me'),
        'SUPABASE_URL':            os.getenv('SUPABASE_URL', ''),
        'SUPABASE_KEY':            os.getenv('SUPABASE_KEY', ''),
        'MAIL_SERVER':             os.getenv('MAIL_SERVER', 'smtp.gmail.com'),
        'MAIL_PORT':               int(os.getenv('MAIL_PORT', 587)),
        'MAIL_USERNAME':           os.getenv('MAIL_USERNAME', ''),
        'MAIL_PASSWORD':           os.getenv('MAIL_PASSWORD', ''),
        'FRONTEND_URL':            os.getenv('FRONTEND_URL', 'http://localhost:5000'),
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SECURE':   os.getenv('FLASK_ENV') == 'production',
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'RAZORPAY_KEY_ID':         os.getenv('RAZORPAY_KEY_ID', ''),
        'RAZORPAY_KEY_SECRET':     os.getenv('RAZORPAY_KEY_SECRET', ''),
        # Flask-Compress settings
        'COMPRESS_REGISTER':       True,
        'COMPRESS_MIMETYPES':      [
            'text/html', 'text/css', 'text/javascript',
            'application/javascript', 'application/json',
            'image/svg+xml',
        ],
        'COMPRESS_LEVEL':          6,   # Good balance of speed vs ratio
        'COMPRESS_MIN_SIZE':       500, # Only compress if > 500 bytes
    })

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins = [
        app.config['FRONTEND_URL'],
        'http://127.0.0.1:5000',
        'http://localhost:5000',
    ]
    # Add Vercel preview URLs if set
    vercel_url = os.getenv('VERCEL_URL', '')
    if vercel_url:
        allowed_origins.append(f'https://{vercel_url}')

    CORS(app, supports_credentials=True, origins=allowed_origins)

    # ── Database ──────────────────────────────────────────────────────────────
    from database import init_db
    init_db(app)
    # Auto-seed on startup when AUTO_SEED=true (set this in Render env vars)
    if os.getenv('AUTO_SEED') == 'true':
        try:
            from seed import seed
            seed()
            print('[APP] Auto-seed completed.')
        except Exception as e:
            print(f'[APP] Auto-seed skipped: {e}')

    # ── Rate limiter ──────────────────────────────────────────────────────────
    from extensions import limiter
    limiter.init_app(app)

    # ── Gzip compression (dramatically reduces JS/CSS/JSON transfer size) ─────
    try:
        from flask_compress import Compress
        Compress(app)
        print('[APP] Flask-Compress enabled (gzip)')
    except ImportError:
        print('[APP] flask-compress not installed — run: pip install flask-compress --break-system-packages')

    # ── SocketIO ──────────────────────────────────────────────────────────────
    socketio.init_app(
        app,
        cors_allowed_origins='*',
        async_mode='eventlet',
        logger=False,
        engineio_logger=False,
        # Ping settings — keep connections alive but don't spam
        ping_timeout=60,
        ping_interval=25,
    )

    # ── API Blueprints ────────────────────────────────────────────────────────
    from routes.auth_routes         import auth_bp
    from routes.auction_routes      import auction_bp
    from routes.wallet_routes       import wallet_bp
    from routes.user_routes         import user_bp
    from routes.notification_routes import notif_bp
    from routes.watchlist_routes    import watchlist_bp
    from routes.order_routes        import order_bp

    app.register_blueprint(auth_bp,       url_prefix='/api/auth')
    app.register_blueprint(auction_bp,    url_prefix='/api/auctions')
    app.register_blueprint(wallet_bp,     url_prefix='/api/wallet')
    app.register_blueprint(user_bp,       url_prefix='/api/user')
    app.register_blueprint(notif_bp,      url_prefix='/api/notifications')
    app.register_blueprint(watchlist_bp,  url_prefix='/api/watchlist')
    app.register_blueprint(order_bp,      url_prefix='/api/orders')

    from routes.socket_events import register_socket_events
    register_socket_events(socketio)

    # ── Static file caching ───────────────────────────────────────────────────
    @app.after_request
    def add_cache_headers(response):
        path = request.path
        # Cache CSS and JS for 7 days (they're fingerprinted by Flask's send_static_file)
        if path.startswith('/static/') and (path.endswith('.css') or path.endswith('.js')):
            response.headers['Cache-Control'] = 'public, max-age=604800, immutable'
        # Cache images for 30 days
        elif path.startswith('/static/') and any(path.endswith(ext) for ext in ('.png','.jpg','.jpeg','.webp','.svg','.ico')):
            response.headers['Cache-Control'] = 'public, max-age=2592000'
        # Don't cache HTML pages or API responses
        elif path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    # ── Page routes ──────────────────────────────────────────────────────────
    @app.route('/')
    @app.route('/login')
    def login_page():         return render_template('login.html')

    @app.route('/signup')
    def signup_page():        return render_template('signup.html')

    @app.route('/dashboard')
    def dashboard_page():     return render_template('dashboard.html')

    @app.route('/auction')
    @app.route('/auction/<auction_id>')
    def auction_page(auction_id=None): return render_template('auction.html')

    @app.route('/create')
    def create_page():        return render_template('create.html')

    @app.route('/wallet')
    def wallet_page():        return render_template('wallet.html')

    @app.route('/settings')
    def settings_page():      return render_template('settings.html')

    @app.route('/notifications')
    def notifications_page(): return render_template('notifications.html')

    @app.route('/watchlist')
    def watchlist_page():     return render_template('watchlist.html')

    @app.route('/verify-email')
    def verify_email_page():  return render_template('verify_email.html')

    @app.route('/reset-password')
    def reset_password_page(): return render_template('reset_password.html')

    @app.route('/order/<order_id>')
    def order_page(order_id): return render_template('order.html')

    @app.route('/my-orders')
    def my_orders_page():     return render_template('my_orders.html')

    # ── Health check (used by Render/Vercel) ─────────────────────────────────
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'flexy-backend'}, 200

    # ── Admin seed endpoint (protected by SEED_SECRET env var) ───────────────
    # Usage: POST /api/admin/seed  with header  X-Seed-Secret: <your SEED_SECRET value>
    # Set SEED_SECRET in Render environment variables.
    # This lets you re-seed the DB any time without needing shell access.
    @app.route('/api/admin/seed', methods=['POST'])
    def admin_seed():
        secret = os.getenv('SEED_SECRET', '')
        if not secret:
            return {'error': 'SEED_SECRET env var not configured'}, 503
        if request.headers.get('X-Seed-Secret') != secret:
            return {'error': 'Unauthorized'}, 401
        try:
            from seed import seed
            seed()
            return {'status': 'ok', 'message': 'Seed completed successfully'}, 200
        except Exception as e:
            return {'status': 'error', 'message': str(e)}, 500

    return app


if __name__ == '__main__':
    app = create_app()
    socketio.run(
        app,
        debug=os.getenv('FLASK_ENV') != 'production',
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )