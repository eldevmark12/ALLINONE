"""
Main Flask Application with WebSocket Support
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity
from flask_socketio import SocketIO, emit, join_room, leave_room
from config import config
from models import db
from models.user import User
from models.smtp import SMTPServer
from models.campaign import Campaign, Recipient
from models.email import FromAddress, EmailTemplate, EmailLog, IMAPAccount
import os
import redis
import json
import threading


# Initialize extensions
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')
jwt = JWTManager()


def create_app(config_name=None):
    """Application factory"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    CORS(app, origins=app.config['CORS_ORIGINS'])
    jwt.init_app(app)
    socketio.init_app(app, message_queue=app.config['SOCKETIO_MESSAGE_QUEUE'])
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    # Register blueprints
    from api import auth, smtp, campaigns, from_addresses, templates, stats
    
    app.register_blueprint(auth.bp, url_prefix='/api/auth')
    app.register_blueprint(smtp.bp, url_prefix='/api/smtp')
    app.register_blueprint(campaigns.bp, url_prefix='/api/campaigns')
    app.register_blueprint(from_addresses.bp, url_prefix='/api/from-addresses')
    app.register_blueprint(templates.bp, url_prefix='/api/templates')
    app.register_blueprint(stats.bp, url_prefix='/api/stats')
    
    # WebSocket event handlers
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection"""
        print(f'Client connected: {request.sid}')
        emit('connected', {'status': 'connected', 'sid': request.sid})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        print(f'Client disconnected: {request.sid}')
    
    @socketio.on('subscribe_campaign')
    def handle_subscribe_campaign(data):
        """Subscribe to campaign updates"""
        campaign_id = data.get('campaign_id')
        if campaign_id:
            room = f'campaign_{campaign_id}'
            join_room(room)
            print(f'Client {request.sid} subscribed to campaign {campaign_id}')
            emit('subscribed', {'campaign_id': campaign_id, 'room': room})
    
    @socketio.on('unsubscribe_campaign')
    def handle_unsubscribe_campaign(data):
        """Unsubscribe from campaign updates"""
        campaign_id = data.get('campaign_id')
        if campaign_id:
            room = f'campaign_{campaign_id}'
            leave_room(room)
            print(f'Client {request.sid} unsubscribed from campaign {campaign_id}')
            emit('unsubscribed', {'campaign_id': campaign_id})
    
    # Start Redis listener thread for campaign updates
    def redis_listener():
        """Listen for campaign updates from Redis pub/sub"""
        redis_url = app.config.get('SOCKETIO_MESSAGE_QUEUE', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        pubsub = r.pubsub()
        pubsub.subscribe('campaign_updates')
        
        print('Redis listener started...')
        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    campaign_id = data.get('campaign_id')
                    if campaign_id:
                        room = f'campaign_{campaign_id}'
                        socketio.emit('campaign_update', data, room=room)
                except Exception as e:
                    print(f'Error processing Redis message: {e}')
    
    # Start Redis listener in background thread
    listener_thread = threading.Thread(target=redis_listener, daemon=True)
    listener_thread.start()
    
    # Health check endpoint
    @app.route('/health')
    def health():
        return jsonify({'status': 'healthy', 'service': 'ALL-in-One Email Platform'}), 200
    
    # Root endpoint - Serve frontend or API info
    @app.route('/')
    def index():
        # Check if frontend build exists
        frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend', 'dist', 'index.html')
        if os.path.exists(frontend_path):
            return send_from_directory(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend', 'dist'), 'index.html')
        
        # Otherwise return API info
        return jsonify({
            'service': 'ALL-in-One Email Platform API',
            'version': '1.0.0',
            'status': 'running',
            'endpoints': {
                'health': '/health',
                'auth': '/api/auth',
                'smtp': '/api/smtp',
                'campaigns': '/api/campaigns',
                'from_addresses': '/api/from-addresses',
                'templates': '/api/templates',
                'stats': '/api/stats'
            }
        }), 200
    
    # Serve static files from frontend build
    @app.route('/<path:path>')
    def serve_static(path):
        frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend', 'dist')
        if os.path.exists(os.path.join(frontend_dist, path)):
            return send_from_directory(frontend_dist, path)
        # If file doesn't exist, return index.html for client-side routing
        if os.path.exists(os.path.join(frontend_dist, 'index.html')):
            return send_from_directory(frontend_dist, 'index.html')
        return jsonify({'error': 'Not found'}), 404
    
    return app


# Create app instance
app = create_app()


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
