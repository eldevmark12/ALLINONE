"""
Association tables for many-to-many relationships
"""
from models import db

# Campaign <-> SMTP Servers (many-to-many)
campaign_smtps = db.Table('campaign_smtps',
    db.Column('campaign_id', db.String(36), db.ForeignKey('campaigns.id'), primary_key=True),
    db.Column('smtp_server_id', db.String(36), db.ForeignKey('smtp_servers.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=db.func.now())
)

# Campaign <-> FROM Addresses (many-to-many)
campaign_froms = db.Table('campaign_froms',
    db.Column('campaign_id', db.String(36), db.ForeignKey('campaigns.id'), primary_key=True),
    db.Column('from_address_id', db.String(36), db.ForeignKey('from_addresses.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=db.func.now())
)

# Verification <-> FROM Addresses (many-to-many)
verification_froms = db.Table('verification_froms',
    db.Column('verification_id', db.String(36), db.ForeignKey('verifications.id'), primary_key=True),
    db.Column('from_address_id', db.String(36), db.ForeignKey('from_addresses.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=db.func.now())
)
