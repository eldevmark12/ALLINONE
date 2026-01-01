"""
Celery Configuration
Background task processing for email campaigns
"""
import os
import redis
from celery import Celery

# Get configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///email_platform.db')

# Initialize Celery
celery = Celery(
    'email_platform',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        'backend.tasks.campaign_tasks',
        'backend.tasks.verification_tasks'
    ]
)

# Configure Celery
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    broker_connection_retry_on_startup=True
)

# Initialize Redis client for locks and pub/sub
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Flask app context for database access
_flask_app = None

def init_celery(app=None):
    """Initialize Celery with Flask app context"""
    global _flask_app
    if app:
        _flask_app = app
        celery.conf.update(app.config)
    return celery

def get_flask_app():
    """Get Flask app instance for database access"""
    global _flask_app
    if _flask_app is None:
        # Create minimal Flask app for database access
        from flask import Flask
        from backend.models import db
        
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        db.init_app(app)
        _flask_app = app
    
    return _flask_app

