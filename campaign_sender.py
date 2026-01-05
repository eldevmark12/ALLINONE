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

# Import SMTP counter function from app.py
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class CampaignSender:
    def __init__(self, config, callback=None, from_file_path=None):
        self.config = config
        self.callback = callback
        self.total_sent = 0
        self.total_failed = 0
        self.running = False
        self.smtp_stats = {}  # Track sent count per SMTP
        self.smtp_failures = {}  # Track failure count per SMTP
        self.disabled_smtps = set()  # Track disabled SMTPs
        self.smtp_lock = threading.Lock()
        self.from_index = 0
        self.recipient_index = 0
        self.from_file_path = from_file_path
        self.used_from_emails = set()  # Track used from emails
        self.max_smtp_failures = 5  # Disable SMTP after 5 failures
        
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
            # Track this from email as used
            was_new = from_email not in self.used_from_emails
            self.used_from_emails.add(from_email)
            
            # Remove from email from file immediately if it's newly used
            if was_new and self.from_file_path:
                self.remove_from_email_from_file(from_email)
            
            # Notify about from email count change if this is a new one
            if was_new and self.callback:
                remaining = len(from_emails) - len(self.used_from_emails)
                self.callback({
                    'type': 'from_count_update',
                    'total': len(from_emails),
                    'used': len(self.used_from_emails),
                    'remaining': remaining
                })
        return from_email
    
    def get_next_smtp(self, smtp_servers):
        """Get next active SMTP server (round-robin), skip disabled ones"""
        # Filter active SMTPs that are not disabled
        active_smtps = [
            s for s in smtp_servers 
            if s.get('status') == 'active' and s['username'] not in self.disabled_smtps
        ]
        
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
    
    def increment_smtp_failure(self, smtp_username):
        """Increment failure counter for SMTP and disable if threshold reached"""
        with self.smtp_lock:
            self.smtp_failures[smtp_username] = self.smtp_failures.get(smtp_username, 0) + 1
            
            if self.smtp_failures[smtp_username] >= self.max_smtp_failures:
                self.disabled_smtps.add(smtp_username)
                self.log(f"⚠️ SMTP {smtp_username} DISABLED after {self.smtp_failures[smtp_username]} failures", 'warning')
                return True
        return False
    
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
            
            # ✅ UPDATE SMTP SENT COUNT IN smtp.txt (REAL-TIME)
            try:
                from app import increment_smtp_sent_count
                increment_smtp_sent_count(smtp_server['username'])
            except Exception as counter_error:
                self.log(f"⚠️ Failed to update SMTP counter: {str(counter_error)[:50]}", 'warning')
            
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
            self.increment_smtp_failure(smtp_server['username'])
            self.update_stats()
            error_msg = f"✗ FAILED {recipient} | SMTP Auth Failed: {smtp_server['username']}"
            self.log(error_msg, 'error')
            return False
            
        except Exception as e:
            self.total_failed += 1
            self.increment_smtp_failure(smtp_server['username'])
            self.update_stats()
            error_msg = f"✗ FAILED {recipient} | Error: {str(e)[:100]}"
            self.log(error_msg, 'error')
            return False
    
    def send_campaign(self, recipients, from_emails, smtp_servers, html_content, subject, sender_name):
        """Send campaign to all from emails by cycling through recipients"""
        self.running = True
        self.total_sent = 0
        self.total_failed = 0
        self.smtp_stats = {}
        self.used_from_emails = set()
        
        self.log(f"Starting campaign: {len(recipients)} recipients, {len(from_emails)} from emails, {len([s for s in smtp_servers if s.get('status') == 'active'])} active SMTPs", 'info')
        self.log(f"Will cycle through {len(recipients)} recipients until all {len(from_emails)} from emails are used", 'info')
        
        # Keep sending until all from emails are used
        while len(self.used_from_emails) < len(from_emails) and self.running:
            for recipient in recipients:
                if not self.running:
                    self.log("Campaign stopped by user", 'warning')
                    break
                
                # Check if all from emails have been used
                if len(self.used_from_emails) >= len(from_emails):
                    self.log("All from emails have been used", 'success')
                    break
                
                # Get next from email (round-robin across all from emails)
                from_email = self.get_next_from_email(from_emails)
                if not from_email:
                    self.log("No from emails available", 'error')
                    break
                
                # Get next SMTP (round-robin across recipients, skip disabled)
                smtp_server = self.get_next_smtp(smtp_servers)
                if not smtp_server:
                    self.log("No active SMTP servers available (all may be disabled)", 'error')
                    break
                
                # Send email
                self.send_email(recipient, from_email, smtp_server, html_content, subject, sender_name)
        
        # Log final SMTP statistics
        if self.disabled_smtps:
            self.log(f"Campaign ended with {len(self.disabled_smtps)} SMTP(s) disabled due to failures", 'warning')
        
        # Final cleanup: ensure all used from emails are removed (safety check)
        if self.from_file_path and self.used_from_emails:
            self.remove_used_from_emails()
            self.log(f"Campaign cleanup completed: {len(self.used_from_emails)} from emails processed", 'info')
        
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
    
    def remove_from_email_from_file(self, from_email):
        """Remove a single from email from the from.txt file immediately"""
        try:
            if not os.path.exists(self.from_file_path):
                return
            
            # Read all from emails
            with open(self.from_file_path, 'r') as f:
                all_from_emails = [line.strip() for line in f if line.strip()]
            
            # Remove this specific email if it exists
            if from_email in all_from_emails:
                all_from_emails.remove(from_email)
                
                # Write back remaining emails
                with open(self.from_file_path, 'w') as f:
                    for email in all_from_emails:
                        f.write(f"{email}\n")
            
        except Exception as e:
            self.log(f"Error removing from email {from_email}: {str(e)}", 'error')
    
    def remove_used_from_emails(self):
        """Remove used from emails from the from.txt file (legacy - now done incrementally)"""
        try:
            if not os.path.exists(self.from_file_path):
                return
            
            # Read all from emails
            with open(self.from_file_path, 'r') as f:
                all_from_emails = [line.strip() for line in f if line.strip()]
            
            original_count = len(all_from_emails)
            
            # Filter out used emails (should be already removed, but double-check)
            remaining_emails = [email for email in all_from_emails if email not in self.used_from_emails]
            
            # Write back remaining emails
            with open(self.from_file_path, 'w') as f:
                for email in remaining_emails:
                    f.write(f"{email}\n")
            
            cleaned_up = original_count - len(remaining_emails)
            if cleaned_up > 0:
                self.log(f"Final cleanup: removed {cleaned_up} additional emails", 'info')
            
        except Exception as e:
            self.log(f"Error in final cleanup: {str(e)}", 'error')
    
    def stop(self):
        """Stop the campaign"""
        self.running = False
