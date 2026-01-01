"""
Campaign model
"""
from models import db, generate_uuid
from datetime import datetime


class Campaign(db.Model):
    """Campaign model for email campaigns"""
    
    __tablename__ = 'campaigns'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    campaign_type = db.Column(db.String(20), nullable=False)  # 'test_froms' or 'bulk_sending'
    status = db.Column(db.String(20), default='pending')  # 'pending', 'running', 'paused', 'completed', 'failed'
    
    # Celery background task fields
    celery_task_id = db.Column(db.String(50))  # Celery task ID for background processing
    error = db.Column(db.Text)  # Error message if failed
    
    # Campaign configuration
    template = db.Column(db.Text)  # HTML email template
    subject = db.Column(db.String(500))  # Email subject
    sleep_interval = db.Column(db.Float, default=1.0)  # Delay between emails (seconds)
    
    # SMTP rotation state (for thread-safe rotation)
    smtp_index = db.Column(db.Integer, default=0)  # Current SMTP index
    from_index = db.Column(db.Integer, default=0)  # Current FROM address index
    
    # Statistics
    emails_sent = db.Column(db.Integer, default=0)
    emails_failed = db.Column(db.Integer, default=0)
    
    total_recipients = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    thread_count = db.Column(db.Integer, default=10)
    delay_seconds = db.Column(db.Float, default=1.0)
    retry_count = db.Column(db.Integer, default=5)
    template_id = db.Column(db.String(36), db.ForeignKey('email_templates.id'))
    started_at = db.Column(db.DateTime)
    stopped_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    recipients = db.relationship('Recipient', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    logs = db.relationship('EmailLog', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    smtp_servers = db.relationship('SMTPServer', secondary='campaign_smtps', lazy='dynamic')
    from_addresses = db.relationship('FromAddress', secondary='campaign_froms', lazy='dynamic')
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'campaign_type': self.campaign_type,
            'status': self.status,
            'total_recipients': self.total_recipients,
            'sent_count': self.sent_count,
            'failed_count': self.failed_count,
            'thread_count': self.thread_count,
            'delay_seconds': self.delay_seconds,
            'retry_count': self.retry_count,
            'template_id': self.template_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Campaign {self.name}>'


class Recipient(db.Model):
    """Recipient model for campaign recipients"""
    
    __tablename__ = 'recipients'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    campaign_id = db.Column(db.String(36), db.ForeignKey('campaigns.id'), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'sent', 'failed', 'bounced'
    sent_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'email': self.email,
            'status': self.status,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<Recipient {self.email}>'
