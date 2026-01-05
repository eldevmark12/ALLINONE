import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import uuid
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configuration
TEST_EMAIL = "just@justtrynew.co.site"
IMAP_SERVER = "Imap0001.neo.space"
IMAP_PORT = 993
IMAP_PASSWORD = "Venom@2025"
SMTP_TIMEOUT = 30
MAX_WORKERS = 10
WAIT_TIME = 300  # 5 minutes

tracking_lock = threading.Lock()
sent_tracking_ids = {}

def create_html_message(tracking_id, from_email):
    """Create HTML test message with tracking"""
    html = f"""
    <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; background-color: #f4f4f4; }}
                .container {{ background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .header {{ color: #2c3e50; font-size: 24px; margin-bottom: 20px; }}
                .content {{ color: #34495e; line-height: 1.6; }}
                .tracking {{ background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin-top: 20px; font-family: monospace; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">SMTP Validation Test</div>
                <div class="content">
                    <p>This is an automated test message to verify SMTP delivery.</p>
                    <div class="tracking">
                        <strong>Tracking ID:</strong> {tracking_id}<br>
                        <strong>From:</strong> {from_email}<br>
                        <strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    </div>
                </div>
            </div>
        </body>
    </html>
    """
    return html

def send_test_email(account, callback=None):
    """Send test email via SMTP with tracking"""
    tracking_id = str(uuid.uuid4())
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = account['email']
        msg['To'] = TEST_EMAIL
        msg['Subject'] = f"SMTP Test - {tracking_id[:8]}"
        msg['X-Tracking-ID'] = tracking_id
        
        html_content = create_html_message(tracking_id, account['email'])
        msg.attach(MIMEText(html_content, 'html'))
        
        # Connect and send
        server = smtplib.SMTP(account['host'], int(account['port']), timeout=SMTP_TIMEOUT)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(account['email'], account['password'])
        server.send_message(msg)
        server.quit()
        
        with tracking_lock:
            sent_tracking_ids[tracking_id] = account
        
        # ✅ INCREMENT SMTP SENT COUNTER (validation test email counts too)
        try:
            from app import increment_smtp_sent_count
            increment_smtp_sent_count(account['email'])
        except Exception as counter_error:
            print(f"⚠️ Failed to update SMTP counter: {str(counter_error)[:50]}")
        
        if callback:
            callback({'type': 'success', 'email': account['email'], 'tracking_id': tracking_id})
        
        return {'success': True, 'tracking_id': tracking_id, 'account': account}
        
    except smtplib.SMTPAuthenticationError:
        if callback:
            callback({'type': 'error', 'email': account['email'], 'error': 'Authentication failed'})
        return {'success': False, 'account': account, 'error': 'Authentication failed'}
    except Exception as e:
        if callback:
            callback({'type': 'error', 'email': account['email'], 'error': str(e)[:50]})
        return {'success': False, 'account': account, 'error': str(e)[:50]}

def send_all_emails(accounts, callback=None):
    """Send emails from all accounts in parallel"""
    sent_results = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(send_test_email, account, callback): account for account in accounts}
        
        for future in as_completed(futures):
            result = future.result()
            if result['success']:
                sent_results.append(result)
    
    return sent_results

def check_imap_for_messages(callback=None):
    """Check IMAP inbox and spam for test messages"""
    verified_accounts = []
    
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(TEST_EMAIL, IMAP_PASSWORD)
        
        folders_to_check = ['INBOX', 'Spam', 'Junk', '[Gmail]/Spam', 'INBOX.Spam']
        
        for folder in folders_to_check:
            try:
                status, _ = mail.select(folder)
                if status != 'OK':
                    continue
                
                if callback:
                    callback({'type': 'info', 'message': f'Checking folder: {folder}'})
                
                status, messages = mail.search(None, 'ALL')
                if status != 'OK':
                    continue
                
                message_ids = messages[0].split()
                recent_ids = message_ids[-500:] if len(message_ids) > 500 else message_ids
                
                for msg_id in reversed(recent_ids):
                    try:
                        status, msg_data = mail.fetch(msg_id, '(RFC822)')
                        if status != 'OK':
                            continue
                        
                        email_body = msg_data[0][1]
                        message = email.message_from_bytes(email_body)
                        
                        tracking_id = message.get('X-Tracking-ID', '')
                        
                        if not tracking_id:
                            subject = message.get('Subject', '')
                            if 'SMTP Test' in subject:
                                match = re.search(r'([0-9a-f]{8})', subject)
                                if match:
                                    with tracking_lock:
                                        for tid in sent_tracking_ids.keys():
                                            if tid.startswith(match.group(1)):
                                                tracking_id = tid
                                                break
                        
                        if tracking_id:
                            with tracking_lock:
                                if tracking_id in sent_tracking_ids:
                                    account = sent_tracking_ids[tracking_id]
                                    verified_accounts.append(account)
                                    if callback:
                                        try:
                                            callback({'type': 'validated', 'email': account.get('email', 'Unknown'), 'folder': folder})
                                        except Exception as cb_err:
                                            print(f"Callback error: {cb_err}")
                                    
                    except Exception as e:
                        continue
                        
            except Exception as e:
                if callback:
                    try:
                        callback({'type': 'info', 'message': f'Skipping folder {folder}'})
                    except:
                        pass
                continue
        
        mail.close()
        mail.logout()
        
    except Exception as e:
        if callback:
            callback({'type': 'error', 'message': f'IMAP error: {str(e)}'})
    
    return verified_accounts

def validate_smtp_accounts(accounts, callback=None):
    """Main validation function"""
    if callback:
        callback({'type': 'info', 'message': f'Starting validation for {len(accounts)} accounts'})
    
    # Send test emails
    sent_results = send_all_emails(accounts, callback)
    
    if callback:
        callback({'type': 'info', 'message': f'Sent {len(sent_results)} test emails. Waiting {WAIT_TIME} seconds...'})
    
    # Wait for emails to arrive
    for remaining in range(WAIT_TIME, 0, -30):
        if callback:
            callback({'type': 'wait', 'remaining': remaining})
        time.sleep(30)
    
    # Check for received messages
    if callback:
        callback({'type': 'info', 'message': 'Checking inbox for validation...'})
    
    verified_accounts = check_imap_for_messages(callback)
    
    # Remove duplicates
    unique_verified = []
    seen_emails = set()
    for account in verified_accounts:
        try:
            email = account.get('email', '') if isinstance(account, dict) else ''
            if email and email not in seen_emails:
                unique_verified.append(account)
                seen_emails.add(email)
        except Exception as e:
            print(f"Error processing account: {e}")
            continue
    
    if callback:
        try:
            callback({'type': 'complete', 'validated': len(unique_verified), 'total': len(accounts)})
        except Exception as e:
            print(f"Callback error on complete: {e}")
    
    return unique_verified
