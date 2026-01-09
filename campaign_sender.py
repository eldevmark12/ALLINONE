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
from queue import Queue, Empty

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
        self.disabled_smtps = set()  # Track disabled SMTPs (in memory)
        self.smtp_lock = threading.Lock()
        self.smtp_queue = Queue()  # Thread-safe SMTP distribution queue
        self.from_index = 0
        self.recipient_index = 0
        self.from_file_path = from_file_path
        self.smtp_file_path = os.path.join('Basic', 'smtp.txt')
        self.used_from_emails = set()  # Track used from emails
        self.max_smtp_failures = 5  # Mark SMTP as inactive after 5 consecutive failures
        
        # Load previously disabled/inactive SMTPs from smtp.txt on init
        self._load_disabled_smtps()
    
    def _load_disabled_smtps(self):
        """Load previously disabled/inactive SMTPs from smtp.txt file"""
        try:
            if not os.path.exists(self.smtp_file_path):
                return
            
            with open(self.smtp_file_path, 'r') as f:
                lines = f.readlines()[1:]  # Skip header
                for line in lines:
                    if line.strip():
                        parts = line.strip().split(',')
                        if len(parts) >= 5:
                            username = parts[2].strip()
                            status = parts[4].strip()
                            if status in ['disabled', 'inactive']:
                                self.disabled_smtps.add(username)
                                self.log(f"🔄 Loaded previously {status} SMTP: {username}", 'warning')
        except Exception as e:
            self.log(f"⚠️ Error loading disabled SMTPs: {str(e)}", 'warning')
    
    def _update_smtp_status_in_file(self, smtp_username, new_status):
        """Update SMTP status in smtp.txt file (persist to disk)"""
        try:
            if not os.path.exists(self.smtp_file_path):
                return False
            
            # Read all lines
            with open(self.smtp_file_path, 'r') as f:
                lines = f.readlines()
            
            # Update the specific SMTP's status
            updated = False
            with open(self.smtp_file_path, 'w') as f:
                f.write(lines[0])  # Write header
                for line in lines[1:]:
                    if line.strip():
                        parts = line.strip().split(',')
                        if len(parts) >= 4:
                            current_username = parts[2].strip()
                            if current_username == smtp_username:
                                # Update this SMTP's status
                                sent = parts[5].strip() if len(parts) > 5 else '0'
                                f.write(f"{parts[0]},{parts[1]},{parts[2]},{parts[3]},{new_status},{sent}\n")
                                updated = True
                            else:
                                # Keep other SMTPs unchanged
                                f.write(line)
            
            return updated
        except Exception as e:
            self.log(f"❌ Error updating SMTP status in file: {str(e)}", 'error')
            return False
        
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
    
    def get_next_smtp(self, smtp_servers=None):
        """Get next active SMTP server from thread-safe queue
        
        Args:
            smtp_servers: Optional list of SMTP servers (used only for initialization)
        
        Returns:
            SMTP server dict or None if queue is empty
        """
        try:
            # Try to get SMTP from queue (non-blocking)
            smtp = self.smtp_queue.get_nowait()
            return smtp
        except Empty:
            # Queue is empty, no SMTPs available
            return None
    
    def _initialize_smtp_queue(self, smtp_servers):
        """Initialize SMTP queue with active, non-disabled SMTPs
        
        This should be called once at the start of the campaign to populate
        the queue with available SMTPs. The queue will be consumed as threads
        pick up SMTPs for sending.
        """
        # Filter ONLY active SMTPs that are not in disabled set
        active_smtps = [
            s for s in smtp_servers 
            if s.get('status') == 'active' and s['username'] not in self.disabled_smtps
        ]
        
        self.log(f"📊 SMTP Status: Total={len(smtp_servers)}, Disabled={len(self.disabled_smtps)}, Available={len(active_smtps)}", 'info')
        
        # Create a large pool by duplicating SMTPs (for round-robin effect)
        # Each SMTP is added multiple times to the queue
        smtp_pool = active_smtps * 100  # Multiply by 100 for large campaigns
        
        # Shuffle for randomization
        random.shuffle(smtp_pool)
        
        # Clear queue and populate with SMTP pool
        while not self.smtp_queue.empty():
            try:
                self.smtp_queue.get_nowait()
            except Empty:
                break
        
        for smtp in smtp_pool:
            self.smtp_queue.put(smtp)
        
        self.log(f"📮 Initialized SMTP queue with {self.smtp_queue.qsize()} SMTP instances for distribution", 'info')
    
    def increment_smtp_sent(self, smtp_username):
        """Increment sent counter for SMTP"""
        with self.smtp_lock:
            self.smtp_stats[smtp_username] = self.smtp_stats.get(smtp_username, 0) + 1
    
    def increment_smtp_failure(self, smtp_username):
        """Increment failure counter for SMTP and mark as inactive if threshold reached
        
        When an SMTP reaches the failure threshold:
        1. Add to in-memory disabled set
        2. Update status to 'inactive' in smtp.txt file
        3. Log the marking event
        """
        with self.smtp_lock:
            self.smtp_failures[smtp_username] = self.smtp_failures.get(smtp_username, 0) + 1
            
            if self.smtp_failures[smtp_username] >= self.max_smtp_failures:
                # Add to disabled set (in-memory)
                self.disabled_smtps.add(smtp_username)
                
                # Persist to smtp.txt file immediately (mark as 'inactive')
                success = self._update_smtp_status_in_file(smtp_username, 'inactive')
                
                if success:
                    self.log(f"⚠️ SMTP {smtp_username} marked INACTIVE after {self.smtp_failures[smtp_username]} failures (persisted to file)", 'warning')
                else:
                    self.log(f"⚠️ SMTP {smtp_username} marked INACTIVE after {self.smtp_failures[smtp_username]} failures (file update failed)", 'warning')
                
                return True
        return False
    
    def get_smtp_stats(self):
        """Get SMTP statistics"""
        return dict(self.smtp_stats)
    
    def send_email(self, recipient, from_email, smtp_server, html_content, subject, sender_name):
        """Send single email via SMTP"""
        try:
            # Replace random placeholders in subject and body
            random5 = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
            random_ref = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
            
            # Replace in subject: <randomchar5> → 5 random chars
            personalized_subject = subject.replace('<randomchar5>', random5)
            
            # Replace in body: RANDOM → 10 random chars
            personalized_html = html_content.replace('RANDOM', random_ref)
            
            # Create message
            msg = MIMEMultipart("alternative")
            msg.set_boundary(self.generate_random_boundary())
            
            # Set headers
            msg['From'] = f'{sender_name} <{from_email}>'
            msg['To'] = recipient
            msg['Date'] = email.utils.formatdate(localtime=True)
            msg['Subject'] = personalized_subject
            msg["Message-ID"] = f"<{str(uuid.uuid4())}@mta-{random.randint(1000, 9999)}.i>"
            
            # Check importance setting
            if self.config.get('important') == '1':
                msg['Importance'] = "high"
                msg['X-Priority'] = "1"
            
            # Attach HTML content
            message_html_cleaned = ''.join(char if 32 <= ord(char) < 128 else ' ' for char in personalized_html)
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
        """Send campaign to all from emails by cycling through recipients with multi-threading
        
        Key improvements:
        - Thread-safe SMTP distribution using queue
        - Persistent SMTP disabling to smtp.txt
        - Better error handling and logging
        - Controlled thread pool size
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        self.running = True
        self.total_sent = 0
        self.total_failed = 0
        self.smtp_stats = {}
        self.used_from_emails = set()
        
        # Get thread count from config (default 10, max 50)
        thread_count = int(self.config.get('threads', 10))
        thread_count = min(thread_count, 50)  # Cap at 50 threads for stability
        
        # Initialize SMTP queue for thread-safe distribution
        self._initialize_smtp_queue(smtp_servers)
        
        active_smtp_count = len([s for s in smtp_servers if s.get('status') == 'active' and s['username'] not in self.disabled_smtps])
        
        self.log(f"🚀 Starting campaign: {len(recipients)} recipients, {len(from_emails)} from emails", 'info')
        self.log(f"📊 SMTPs: {active_smtp_count} available, {len(self.disabled_smtps)} disabled", 'info')
        self.log(f"🔧 Using {thread_count} threads for parallel sending", 'info')
        self.log(f"📧 Will cycle through {len(recipients)} recipients until all {len(from_emails)} from emails are used", 'info')
        
        # Create task list: pair each from_email with a recipient
        tasks = []
        recipient_index = 0
        for from_email in from_emails:
            if not self.running:
                break
            recipient = recipients[recipient_index % len(recipients)]
            recipient_index += 1
            tasks.append((from_email, recipient))
        
        self.log(f"📋 Created {len(tasks)} sending tasks", 'info')
        
        # Execute tasks with thread pool
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = {}
            
            for from_email, recipient in tasks:
                if not self.running:
                    break
                
                # Get next SMTP from queue (thread-safe)
                smtp_server = self.get_next_smtp()
                if not smtp_server:
                    self.log("⚠️ No SMTP servers available in queue", 'warning')
                    # Try to refill queue with remaining ACTIVE SMTPs only
                    remaining_smtps = [s for s in smtp_servers if s.get('status') == 'active' and s['username'] not in self.disabled_smtps]
                    if remaining_smtps:
                        self.log(f"🔄 Refilling SMTP queue with {len(remaining_smtps)} active SMTPs", 'info')
                        for smtp in remaining_smtps * 10:  # Add each SMTP 10 times
                            self.smtp_queue.put(smtp)
                        smtp_server = self.get_next_smtp()
                    
                    if not smtp_server:
                        self.log("❌ No active SMTP servers available - STOPPING CAMPAIGN", 'error')
                        self.running = False
                        break
                
                # Submit task
                future = executor.submit(
                    self.send_email, 
                    recipient, 
                    from_email, 
                    smtp_server, 
                    html_content, 
                    subject, 
                    sender_name
                )
                futures[future] = (from_email, recipient, smtp_server)
            
            # Process completed tasks
            for future in as_completed(futures):
                if not self.running:
                    self.log("⚠️ Campaign stopped by user", 'warning')
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                from_email, recipient, smtp_server = futures[future]
                
                try:
                    success = future.result()
                    
                    # Track from email usage
                    if from_email not in self.used_from_emails:
                        self.used_from_emails.add(from_email)
                        
                        # Remove from email from file
                        if self.from_file_path:
                            self.remove_from_email_from_file(from_email)
                        
                        # Notify about from email count change
                        if self.callback:
                            remaining = len(from_emails) - len(self.used_from_emails)
                            self.callback({
                                'type': 'from_count_update',
                                'total': len(from_emails),
                                'used': len(self.used_from_emails),
                                'remaining': remaining
                            })
                
                except Exception as e:
                    self.log(f"✗ Task failed: {str(e)[:100]}", 'error')
        
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
