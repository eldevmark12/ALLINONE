#!/usr/bin/env python3
"""
Standalone Email Campaign Sender
Sends emails using hardcoded SMTPs, recipients, and HTML template.
Only reads from emails from a text file.
"""

import smtplib
import random
import string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import email.utils
from datetime import datetime
import threading
import os
import time
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================================
# HARDCODED CONFIGURATION
# ============================================================================

# Active SMTP Servers (as of January 2026)
SMTP_SERVERS = [
    {
        'host': 'smtp.bajoria.in',
        'port': 587,
        'username': 'anant.kumar@bajoria.in',
        'password': '69s2@gig!5'
    },
    {
        'host': 'mail.al-amoudi.net',
        'port': 587,
        'username': 'ma@al-amoudi.net',
        'password': 'm@!#18!ant'
    },
    {
        'host': 'smtp.centrum.sk',
        'port': 587,
        'username': 'mjmj@centrum.sk',
        'password': 'Nh731273-'
    },
    {
        'host': 'mail.msd-consulting.co.za',
        'port': 587,
        'username': 'tjacobs@msd-consulting.co.za',
        'password': 'GetmeIn@135#!'
    },
    {
        'host': 'mail.atharvrajtranslinks.net',
        'port': 587,
        'username': 'pravinbh@atharvrajtranslinks.net',
        'password': 'Atharva@12345'
    },
    {
        'host': 'mail.atharvrajtranslinks.net',
        'port': 587,
        'username': 'info@atharvrajtranslinks.net',
        'password': 'Atharva@12345'
    },
    {
        'host': 'mail.isianpadu.com',
        'port': 587,
        'username': 'danish.ismail@isianpadu.com',
        'password': 'B89e9pmX!GxQMnBo'
    },
    {
        'host': 'mail.poligon.in',
        'port': 587,
        'username': 'portoffice@phonexgroup.com',
        'password': 'NSDoffice'
    },
    {
        'host': 'mail.buyspectra.com',
        'port': 587,
        'username': 'design3@buyspectra.com',
        'password': 'Design@3spectra'
    }
]

# Test Recipients
RECIPIENTS = [
    'Footmen404@yahoo.com',
    'laststand2026@yahoo.com',
    'azoofozora2026@yahoo.com',
    'bravoeco2026@yahoo.com',
    'Footmen203@yahoo.com',
    'micoland2026@yahoo.com',
    'atombrid2069@yahoo.com',
    'azoofoo2026@yahoo.com',
    'brb4mints@yahoo.com',
    'copermerv2026@yahoo.com'
]

# HTML Email Template
HTML_TEMPLATE = """<html>
<body style="font-family: Arial, sans-serif; padding: 20px;">
    <p>Hi there,</p>
    
    <p>I hope this message finds you well. I wanted to reach out and say hello!</p>
    
    <p>I've been thinking about connecting with you and thought this would be a great opportunity.</p>
    
    <p>Looking forward to hearing from you soon.</p>
    
    <p>Best regards,<br>
    {from_email}
    </p>
</body>
</html>"""

# Campaign Settings
SENDER_NAME = "Support"
SUBJECT_TEMPLATE = "hello {random5}"
THREAD_COUNT = 8
SLEEP_TIME = 1  # Seconds between emails (per thread)
FROM_FILE = "from.txt"  # File containing from emails (one per line)

# ============================================================================
# CAMPAIGN SENDER CLASS
# ============================================================================

class StandaloneCampaign:
    def __init__(self):
        self.smtp_queue = Queue()
        self.smtp_lock = threading.Lock()
        self.queue_refilling = False
        self.disabled_smtps = set()
        self.smtp_failures = {}
        self.max_smtp_failures = 5
        self.used_from_emails = set()
        self.total_sent = 0
        self.total_failed = 0
        self.running = False
        
        # Multiply SMTPs for queue (100 copies each for large campaigns)
        for smtp in SMTP_SERVERS:
            for _ in range(100):
                self.smtp_queue.put(smtp.copy())
        
    def log(self, message, level='INFO'):
        """Print log message with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        icon = {
            'INFO': 'ℹ️',
            'SUCCESS': '✅',
            'WARNING': '⚠️',
            'ERROR': '❌'
        }.get(level, 'ℹ️')
        print(f"[{timestamp}] {icon} {message}")
    
    def get_next_smtp(self):
        """Get next available SMTP from queue (skip disabled ones)"""
        max_attempts = 100
        for _ in range(max_attempts):
            try:
                smtp = self.smtp_queue.get_nowait()
                # Check if this SMTP was disabled
                if smtp['username'] not in self.disabled_smtps:
                    return smtp
            except Empty:
                return None
        return None
    
    def increment_smtp_failure(self, smtp_username):
        """Track SMTP failures and disable after threshold"""
        with self.smtp_lock:
            # Skip if already disabled
            if smtp_username in self.disabled_smtps:
                return False
            
            self.smtp_failures[smtp_username] = self.smtp_failures.get(smtp_username, 0) + 1
            
            # Mark inactive on FIRST time hitting threshold
            if self.smtp_failures[smtp_username] == self.max_smtp_failures:
                self.disabled_smtps.add(smtp_username)
                self.log(f"⚠️ SMTP {smtp_username} marked INACTIVE after {self.max_smtp_failures} failures", 'WARNING')
                return True
        return False
    
    def send_email(self, from_email, recipient, smtp_server):
        """Send a single email"""
        try:
            # Generate random string for subject
            random5 = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
            subject = SUBJECT_TEMPLATE.replace('{random5}', random5)
            
            # Prepare HTML with from_email
            html_content = HTML_TEMPLATE.replace('{from_email}', from_email)
            
            # Create message
            msg = MIMEMultipart("alternative")
            msg['From'] = f'{SENDER_NAME} <{from_email}>' if SENDER_NAME else from_email
            msg['To'] = recipient
            msg['Date'] = email.utils.formatdate(localtime=True)
            msg['Subject'] = subject
            msg['Message-ID'] = email.utils.make_msgid()
            
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send via SMTP
            with smtplib.SMTP(smtp_server['host'], smtp_server['port'], timeout=30) as server:
                server.starttls()
                server.login(smtp_server['username'], smtp_server['password'])
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            self.log(f"❌ Error sending to {recipient} from {from_email}: {str(e)[:100]}", 'ERROR')
            return False
    
    def _send_email_with_smtp_fetch(self, from_email, recipient, smtp_servers, max_retries=3):
        """Worker function: Fetch SMTP when ready to send (not during task creation)"""
        smtp_server = None
        
        for attempt in range(max_retries):
            # Get SMTP from queue
            smtp_server = self.get_next_smtp()
            
            if smtp_server:
                break
            
            # Queue empty - refill it (thread-safe)
            with self.smtp_lock:
                if self.smtp_queue.qsize() > 0:
                    continue  # Another thread already refilled
                
                if self.queue_refilling:
                    time.sleep(0.1)  # Wait for other thread to finish refilling
                    continue
                else:
                    self.queue_refilling = True
                    
                    # Refill queue with non-disabled SMTPs
                    remaining_smtps = [s for s in SMTP_SERVERS if s['username'] not in self.disabled_smtps]
                    
                    if remaining_smtps:
                        self.log(f"🔄 Refilling SMTP queue with {len(remaining_smtps)} active SMTPs × 100", 'INFO')
                        for smtp in remaining_smtps:
                            for _ in range(100):
                                self.smtp_queue.put(smtp.copy())
                    else:
                        self.log("⚠️ No active SMTPs available! All disabled.", 'WARNING')
                    
                    self.queue_refilling = False
        
        if not smtp_server:
            self.log(f"⚠️ No SMTP available for {recipient}", 'WARNING')
            return False
        
        # Send email
        success = self.send_email(from_email, recipient, smtp_server)
        
        if success:
            # Return SMTP to queue for reuse
            if smtp_server['username'] not in self.disabled_smtps:
                self.smtp_queue.put(smtp_server)
        else:
            # Track failure
            self.increment_smtp_failure(smtp_server['username'])
        
        return success
    
    def load_from_emails(self):
        """Load from emails from text file"""
        if not os.path.exists(FROM_FILE):
            self.log(f"❌ From file not found: {FROM_FILE}", 'ERROR')
            return []
        
        with open(FROM_FILE, 'r', encoding='utf-8') as f:
            from_emails = [line.strip() for line in f if line.strip()]
        
        self.log(f"📧 Loaded {len(from_emails)} from emails from {FROM_FILE}", 'SUCCESS')
        return from_emails
    
    def run_campaign(self):
        """Main campaign execution"""
        self.running = True
        start_time = datetime.now()
        
        self.log("=" * 60, 'INFO')
        self.log("🚀 STANDALONE EMAIL CAMPAIGN STARTING", 'SUCCESS')
        self.log("=" * 60, 'INFO')
        
        # Load from emails
        from_emails = self.load_from_emails()
        if not from_emails:
            self.log("❌ No from emails loaded. Exiting.", 'ERROR')
            return
        
        # Display configuration
        self.log(f"📊 Configuration:", 'INFO')
        self.log(f"   • SMTP Servers: {len(SMTP_SERVERS)}", 'INFO')
        self.log(f"   • Recipients: {len(RECIPIENTS)}", 'INFO')
        self.log(f"   • From Emails: {len(from_emails)}", 'INFO')
        self.log(f"   • Threads: {THREAD_COUNT}", 'INFO')
        self.log(f"   • Total Emails: {len(from_emails) * len(RECIPIENTS):,}", 'INFO')
        self.log("", 'INFO')
        
        # Prepare tasks (from_email, recipient pairs)
        tasks = []
        for from_email in from_emails:
            for recipient in RECIPIENTS:
                tasks.append((from_email, recipient))
        
        self.log(f"📝 Created {len(tasks):,} email tasks", 'INFO')
        self.log(f"⏱️ Starting campaign with {THREAD_COUNT} threads...", 'INFO')
        self.log("", 'INFO')
        
        # Execute with thread pool
        with ThreadPoolExecutor(max_workers=THREAD_COUNT) as executor:
            futures = {}
            
            for from_email, recipient in tasks:
                if not self.running:
                    break
                    
                future = executor.submit(
                    self._send_email_with_smtp_fetch,
                    from_email,
                    recipient,
                    SMTP_SERVERS
                )
                futures[future] = (from_email, recipient)
            
            # Process results
            for future in as_completed(futures):
                if not self.running:
                    self.log("⚠️ Campaign stopped", 'WARNING')
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                from_email, recipient = futures[future]
                
                try:
                    success = future.result()
                    
                    if success:
                        self.total_sent += 1
                        
                        # Mark from email as used
                        if from_email not in self.used_from_emails:
                            self.used_from_emails.add(from_email)
                        
                        # Log progress every 10 emails
                        if self.total_sent % 10 == 0:
                            progress = (self.total_sent / len(tasks)) * 100
                            self.log(
                                f"✅ Progress: {self.total_sent:,}/{len(tasks):,} ({progress:.1f}%) | "
                                f"Failed: {self.total_failed} | "
                                f"Active SMTPs: {len(SMTP_SERVERS) - len(self.disabled_smtps)}",
                                'SUCCESS'
                            )
                    else:
                        self.total_failed += 1
                        
                except Exception as e:
                    self.total_failed += 1
                    self.log(f"❌ Task error: {str(e)[:100]}", 'ERROR')
                
                # Sleep between emails (optional)
                if SLEEP_TIME > 0:
                    time.sleep(SLEEP_TIME / THREAD_COUNT)
        
        # Campaign summary
        duration = (datetime.now() - start_time).total_seconds()
        
        self.log("", 'INFO')
        self.log("=" * 60, 'INFO')
        self.log("📊 CAMPAIGN COMPLETED", 'SUCCESS')
        self.log("=" * 60, 'INFO')
        self.log(f"✅ Total Sent: {self.total_sent:,}", 'SUCCESS')
        self.log(f"❌ Total Failed: {self.total_failed:,}", 'ERROR' if self.total_failed > 0 else 'INFO')
        self.log(f"📧 Unique From Emails Used: {len(self.used_from_emails)}", 'INFO')
        self.log(f"⚠️ Disabled SMTPs: {len(self.disabled_smtps)}", 'WARNING' if self.disabled_smtps else 'INFO')
        self.log(f"⏱️ Duration: {int(duration)}s ({duration/60:.1f} minutes)", 'INFO')
        self.log(f"🚀 Rate: {self.total_sent/duration:.1f} emails/second", 'INFO')
        self.log("=" * 60, 'INFO')
        
        if self.disabled_smtps:
            self.log("⚠️ Disabled SMTP servers:", 'WARNING')
            for smtp_user in self.disabled_smtps:
                failures = self.smtp_failures.get(smtp_user, 0)
                self.log(f"   • {smtp_user} ({failures} failures)", 'WARNING')

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  STANDALONE EMAIL CAMPAIGN SENDER")
    print("  Version 1.0 - January 2026")
    print("=" * 60 + "\n")
    
    # Check if from.txt exists
    if not os.path.exists(FROM_FILE):
        print(f"❌ ERROR: {FROM_FILE} not found!")
        print(f"📝 Please create {FROM_FILE} with one email per line.")
        print("\nExample from.txt:")
        print("sender1@example.com")
        print("sender2@example.com")
        print("sender3@example.com")
        exit(1)
    
    # Confirm start
    print(f"📊 Configuration:")
    print(f"   • SMTPs: {len(SMTP_SERVERS)} servers")
    print(f"   • Recipients: {len(RECIPIENTS)} addresses")
    print(f"   • From File: {FROM_FILE}")
    print(f"   • Threads: {THREAD_COUNT}")
    print(f"   • Sleep Time: {SLEEP_TIME}s")
    print()
    
    response = input("🚀 Start campaign? (yes/no): ").strip().lower()
    if response != 'yes':
        print("❌ Campaign cancelled.")
        exit(0)
    
    print()
    
    # Run campaign
    campaign = StandaloneCampaign()
    try:
        campaign.run_campaign()
    except KeyboardInterrupt:
        print("\n⚠️ Campaign interrupted by user (Ctrl+C)")
        campaign.running = False
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Campaign script finished.\n")
