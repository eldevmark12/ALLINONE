"""
SMTP Server model
"""
from models import db, generate_uuid
from datetime import datetime
from utils.encryption import encrypt_password, decrypt_password


class SMTPServer(db.Model):
    """SMTP Server model for email sending"""
    
    __tablename__ = 'smtp_servers'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(255), nullable=False)
    password_encrypted = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='active')  # 'active', 'failed', 'disabled'
    
    # Failure tracking (for auto-disable)
    failures = db.Column(db.Integer, default=0)  # Total failures
    successes = db.Column(db.Integer, default=0)  # Total successes
    failure_count = db.Column(db.Integer, default=0)  # Legacy field
    success_count = db.Column(db.Integer, default=0)  # Legacy field
    
    last_used = db.Column(db.DateTime)
    last_error = db.Column(db.Text)  # Last error message
    last_error_at = db.Column(db.DateTime)  # When last error occurred
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Encrypt and set password"""
        self.password_encrypted = encrypt_password(password)
    
    def get_password(self):
        """Decrypt and return password"""
        return decrypt_password(self.password_encrypted)
    
    def to_dict(self, include_password=False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'status': self.status,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_password:
            data['password'] = self.get_password()
        return data
    
    def __repr__(self):
        return f'<SMTPServer {self.username}@{self.host}:{self.port}>'
