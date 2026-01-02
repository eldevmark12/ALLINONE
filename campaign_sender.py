import smtplib
import random
import string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import email.utils
from datetime import datetime
import threading
import uuid
import time
import os

class CampaignSender:
    def __init__(self, config, callback=None):
        self.config = config
        self.callback = callback
        self.total_sent = 0
        self.total_failed = 0
        self.running = False
        self.smtp_stats = {}  # Track sent count per SMTP
        self.smtp_lock = threading.Lock()
        self.from_index = 0
        self.recipient_index = 0
        
    def log(self, message, log_type='info'):
        """Send log message via callback"""
        if self.callback:
            self.callback({'type': 'log', 'message': message, 'log_type': log_type})
    
    def update_stats(self):
        """Send stats update via callback"""
        if self.callback:
            self.callback({
                'type': 'stats',
                'sent': self.total_sent,
                'failed': self.total_failed
            })
    
    def generate_random_boundary(self):
        """Generate random boundary for email"""
        return ''.join(random.choice(string.digits) for _ in range(36))
    
    def get_next_from_email(self, from_emails):
        """Get next from email (round-robin)"""
        if not from_emails:
            return None
        
        with self.smtp_lock:
            if self.from_index >= len(from_emails):
                self.from_index = 0
            from_email = from_emails[self.from_index]
            self.from_index += 1
        return from_email
    
    def get_next_smtp(self, smtp_servers):
        """Get next active SMTP server (round-robin)"""
        active_smtps = [s for s in smtp_servers if s.get('status') == 'active']
        if not active_smtps:
            return None
        
        with self.smtp_lock:
            if self.recipient_index >= len(active_smtps):
                self.recipient_index = 0
            smtp = active_smtps[self.recipient_index]
            self.recipient_index += 1
        return smtp
    
    def increment_smtp_sent(self, smtp_username):
        """Increment sent counter for SMTP"""
        with self.smtp_lock:
            self.smtp_stats[smtp_username] = self.smtp_stats.get(smtp_username, 0) + 1
    
    def get_smtp_stats(self):
        """Get SMTP statistics"""
        return dict(self.smtp_stats)
    
    def send_email(self, recipient, from_email, smtp_server, html_content, subject, sender_name):
        """Send single email via SMTP"""
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg.set_boundary(self.generate_random_boundary())
            
            # Set headers
            msg['From'] = f'{sender_name} <{from_email}>'
            msg['To'] = recipient
            msg['Date'] = email.utils.formatdate(localtime=True)
            msg['Subject'] = subject
            msg["Message-ID"] = f"<{str(uuid.uuid4())}@mta-{random.randint(1000, 9999)}.i>"
            
            # Check importance setting
            if self.config.get('important') == '1':
                msg['Importance'] = "high"
                msg['X-Priority'] = "1"
            
            # Attach HTML content
            message_html_cleaned = ''.join(char if 32 <= ord(char) < 128 else ' ' for char in html_content)
            letterx = MIMEText(message_html_cleaned, "html")
            msg.attach(letterx)
            
            # Connect to SMTP server
            server = smtplib.SMTP(smtp_server['host'], int(smtp_server['port']), timeout=30)
            
            # Enable debug if configured
            if self.config.get('debug') == '1':
                server.set_debuglevel(1)
            
            # STARTTLS
            try:
                server.starttls()
            except Exception as tls_error:
                self.log(f"STARTTLS warning for {smtp_server['host']}: {str(tls_error)[:50]}", 'warning')
            
            # Login
            server.login(smtp_server['username'], smtp_server['password'])
            
            # Send email
            server.sendmail(smtp_server['username'], [recipient], msg.as_string())
            server.quit()
            
            # Update counters
            self.total_sent += 1
            self.increment_smtp_sent(smtp_server['username'])
            self.update_stats()
            
            # Log success
            success_msg = f"✓ SENT to {recipient} | From: {from_email} | SMTP: {smtp_server['username']} | {self.total_sent} sent"
            self.log(success_msg, 'success')
            
            # Sleep if configured
            sleep_time = float(self.config.get('sleeptime', 0))
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            self.total_failed += 1
            self.update_stats()
            error_msg = f"✗ FAILED {recipient} | SMTP Auth Failed: {smtp_server['username']}"
            self.log(error_msg, 'error')
            return False
            
        except Exception as e:
            self.total_failed += 1
            self.update_stats()
            error_msg = f"✗ FAILED {recipient} | Error: {str(e)[:100]}"
            self.log(error_msg, 'error')
            return False
    
    def send_campaign(self, recipients, from_emails, smtp_servers, html_content, subject, sender_name):
        """Send campaign to all recipients"""
        self.running = True
        self.total_sent = 0
        self.total_failed = 0
        self.smtp_stats = {}
        
        self.log(f"Starting campaign: {len(recipients)} recipients, {len(from_emails)} from emails, {len([s for s in smtp_servers if s.get('status') == 'active'])} active SMTPs", 'info')
        
        for recipient in recipients:
            if not self.running:
                self.log("Campaign stopped by user", 'warning')
                break
            
            # Get next from email (round-robin across all from emails)
            from_email = self.get_next_from_email(from_emails)
            if not from_email:
                self.log("No from emails available", 'error')
                break
            
            # Get next SMTP (round-robin across recipients)
            smtp_server = self.get_next_smtp(smtp_servers)
            if not smtp_server:
                self.log("No active SMTP servers available", 'error')
                break
            
            # Send email
            self.send_email(recipient, from_email, smtp_server, html_content, subject, sender_name)
        
        # Campaign complete
        self.running = False
        if self.callback:
            self.callback({
                'type': 'complete',
                'sent': self.total_sent,
                'failed': self.total_failed,
                'smtp_stats': self.get_smtp_stats()
            })
        
        self.log(f"Campaign completed: {self.total_sent} sent, {self.total_failed} failed", 'success')
    
    def stop(self):
        """Stop the campaign"""
        self.running = False
