import os
import json
import threading
import subprocess
import configparser
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import time

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['SESSION_TYPE'] = 'filesystem'

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global variables
campaign_process = None
campaign_running = False
campaign_stats = {
    'total_sent': 0,
    'total_failed': 0,
    'start_time': None,
    'status': 'idle'
}
campaign_logs = []  # Store campaign logs
campaign_lock = threading.Lock()

# Monitored email data (from external email monitoring)
monitored_data = {
    'total_accounts': 0,
    'total_emails': 0,
    'unique_froms': 0,
    'accounts': {},  # account_name: {from_emails: [], emails: [], last_email: ''}
    'last_update': None
}
monitored_lock = threading.Lock()

# File to store active/inactive status for monitored from emails
from_status_file = os.path.join('Basic', 'sending_from_status.json')

def load_from_status():
    """Load active/inactive status from file"""
    try:
        if os.path.exists(from_status_file):
            with open(from_status_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading from status: {e}")
        return {}

def save_from_status(status_dict):
    """Save active/inactive status to file"""
    try:
        with open(from_status_file, 'w') as f:
            json.dump(status_dict, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving from status: {e}")
        return False

def get_from_status(email):
    """Get status for a specific email (defaults to 'active' for new emails)"""
    status_dict = load_from_status()
    return status_dict.get(email, 'active')

def set_from_status(email, status):
    """Set status for a specific email"""
    status_dict = load_from_status()
    status_dict[email] = status
    return save_from_status(status_dict)

def ensure_single_status(email):
    """Ensure email only exists in one status - remove duplicates"""
    status_dict = load_from_status()
    # Email can only have one status in the dict, but this helps clean up any issues
    return status_dict.get(email)

def remove_duplicates_from_status():
    """Remove any duplicate entries and ensure each email has only one status"""
    status_dict = load_from_status()
    # JSON keys are unique by nature, so this is already handled
    # But we can clean up any empty or invalid entries
    cleaned = {k: v for k, v in status_dict.items() if k and '@' in k and v in ['active', 'inactive']}
    save_from_status(cleaned)
    return len(status_dict) - len(cleaned)  # Return number of duplicates removed

def add_or_update_from_email(email, status='active'):
    """Add new from_email or update if exists (prevents duplicates)"""
    status_dict = load_from_status()
    
    # Check if exists
    if email in status_dict:
        # If exists and is inactive, activate it
        if status_dict[email] == 'inactive' and status == 'active':
            status_dict[email] = 'active'
            save_from_status(status_dict)
            return 'updated'  # Was inactive, now active
        return 'exists'  # Already exists with same or different status
    
    # Add new email
    status_dict[email] = status
    save_from_status(status_dict)
    return 'added'

PASSWORD = os.getenv('PASSWORD', '@OLDISGOLD2026@')
BASIC_FOLDER = 'Basic'

# Authentication decorator
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        password = data.get('password', '')
        
        if password == PASSWORD:
            session['logged_in'] = True
            if request.is_json:
                return jsonify({'success': True})
            return redirect(url_for('dashboard'))
        else:
            if request.is_json:
                return jsonify({'success': False, 'error': 'Invalid password'}), 401
            return render_template('login.html', error='Invalid password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', stats=campaign_stats)

@app.route('/smtp')
@login_required
def smtp_management():
    return render_template('smtp.html')

@app.route('/emails')
@login_required
def email_management():
    return render_template('emails.html')

@app.route('/template')
@login_required
def template_editor():
    return render_template('template.html')

@app.route('/campaign')
@login_required
def campaign_settings():
    return render_template('campaign.html')

@app.route('/sending')
@login_required
def sending_page():
    return render_template('sending.html')

# API Routes
@app.route('/api/health')
def health():
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'campaign_running': campaign_running
    })

@app.route('/api/smtp/list', methods=['GET'])
@login_required
def get_smtp_list():
    try:
        smtp_file = os.path.join(BASIC_FOLDER, 'smtp.txt')
        if os.path.exists(smtp_file):
            with open(smtp_file, 'r') as f:
                lines = f.readlines()
                servers = []
                for i, line in enumerate(lines[1:], 1):  # Skip header
                    if line.strip():
                        parts = line.strip().split(',')
                        if len(parts) >= 4:
                            status = parts[4] if len(parts) > 4 else 'inactive'
                            sent = int(parts[5]) if len(parts) > 5 else 0
                            servers.append({
                                'id': i,
                                'host': parts[0].strip(),
                                'port': parts[1].strip(),
                                'username': parts[2].strip(),
                                'email': parts[2].strip(),
                                'password': parts[3].strip(),
                                'status': status.strip(),
                                'sent': sent
                            })
                return jsonify({'success': True, 'servers': servers})
        return jsonify({'success': True, 'servers': []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/smtp/save', methods=['POST'])
@login_required
def save_smtp_list():
    try:
        data = request.get_json()
        servers = data.get('servers', [])
        
        smtp_file = os.path.join(BASIC_FOLDER, 'smtp.txt')
        with open(smtp_file, 'w') as f:
            f.write('host,port,username,password,status,sent\n')
            for server in servers:
                status = server.get('status', 'inactive')
                sent = server.get('sent', 0)
                email = server.get('username', server.get('email', ''))
                f.write(f"{server['host']},{server['port']},{email},{server['password']},{status},{sent}\n")
        
        return jsonify({'success': True, 'message': 'SMTP servers saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/smtp/validate', methods=['POST'])
@login_required
def validate_smtp():
    try:
        data = request.get_json()
        servers = data.get('servers', [])
        
        if not servers:
            return jsonify({'success': False, 'error': 'No servers to validate'}), 400
        
        # Format servers for validation
        accounts = []
        for server in servers:
            accounts.append({
                'email': server.get('username', server.get('email', '')),
                'password': server['password'],
                'host': server['host'],
                'port': server['port']
            })
        
        # Start validation in background thread
        thread = threading.Thread(target=run_smtp_validation, args=(accounts,))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Validation started'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def run_smtp_validation(accounts):
    """Run SMTP validation in background"""
    validation_stats = {
        'total': len(accounts),
        'sent': 0,
        'failed': 0,
        'validated': 0
    }
    
    try:
        from smtp_validator import validate_smtp_accounts
        
        def validation_callback(event):
            try:
                if event['type'] == 'success':
                    validation_stats['sent'] += 1
                    socketio.emit('validation_log', {'message': f"✓ Sent test from {event['email']}"})
                    socketio.emit('validation_stats', validation_stats)
                    
                elif event['type'] == 'error':
                    validation_stats['failed'] += 1
                    socketio.emit('validation_log', {'message': f"✗ Failed {event['email']}: {event.get('error', 'Unknown')}"})
                    socketio.emit('validation_stats', validation_stats)
                    
                elif event['type'] == 'validated':
                    socketio.emit('validation_log', {'message': f"✓ Validated {event['email']} (found in {event['folder']})"})
                    
                elif event['type'] == 'info':
                    socketio.emit('validation_log', {'message': event['message']})
                    
                elif event['type'] == 'wait':
                    socketio.emit('validation_log', {'message': f"Waiting... {event['remaining']} seconds remaining"})
                    
                elif event['type'] == 'complete':
                    validation_stats['validated'] = event['validated']
                    socketio.emit('validation_log', {'message': f"✅ Complete: {event['validated']}/{event['total']} validated"})
                    socketio.emit('validation_stats', validation_stats)
                    
            except Exception as e:
                print(f"Callback error: {e}")
        
        # Run validation
        validated = validate_smtp_accounts(accounts, validation_callback)
        
        # Update SMTP file with validation results
        smtp_file = os.path.join(BASIC_FOLDER, 'smtp.txt')
        if os.path.exists(smtp_file):
            with open(smtp_file, 'r') as f:
                lines = f.readlines()
            
            # Build set of validated emails
            validated_emails = set()
            for acc in validated:
                if isinstance(acc, dict) and 'email' in acc:
                    validated_emails.add(acc['email'])
            
            # Write updated file
            with open(smtp_file, 'w') as f:
                f.write('host,port,username,password,status,sent\n')
                for line in lines[1:]:  # Skip header
                    if line.strip():
                        parts = line.strip().split(',')
                        if len(parts) >= 4:
                            email = parts[2]
                            status = 'active' if email in validated_emails else 'inactive'
                            sent = int(parts[5]) if len(parts) > 5 else 0
                            f.write(f"{parts[0]},{parts[1]},{parts[2]},{parts[3]},{status},{sent}\n")
        
        # Emit completion event
        socketio.emit('validation_complete', {'validated': len(validated_emails), 'total': len(accounts)})
        
    except Exception as e:
        print(f"Validation error: {e}")
        socketio.emit('validation_log', {'message': f'Error: {str(e)}'})

@app.route('/api/emails/list', methods=['GET'])
@login_required
def get_email_list():
    try:
        config_file = os.path.join(BASIC_FOLDER, 'config.ini')
        import configparser
        config = configparser.ConfigParser()
        config.read(config_file)
        
        email_file = config['Settings']['emailspath']
        email_path = os.path.join(BASIC_FOLDER, email_file)
        
        if os.path.exists(email_path):
            with open(email_path, 'r') as f:
                emails = [line.strip() for line in f if line.strip()]
                return jsonify({'success': True, 'emails': emails, 'count': len(emails)})
        return jsonify({'success': True, 'emails': [], 'count': 0})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/emails/save', methods=['POST'])
@login_required
def save_email_list():
    try:
        data = request.get_json()
        emails = data.get('emails', [])
        
        config_file = os.path.join(BASIC_FOLDER, 'config.ini')
        import configparser
        config = configparser.ConfigParser()
        config.read(config_file)
        
        email_file = config['Settings']['emailspath']
        email_path = os.path.join(BASIC_FOLDER, email_file)
        
        with open(email_path, 'w') as f:
            for email in emails:
                if email.strip():
                    f.write(email.strip() + '\n')
        
        return jsonify({'success': True, 'message': f'{len(emails)} emails saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/config/get', methods=['GET'])
@login_required
def get_config():
    try:
        config_file = os.path.join(BASIC_FOLDER, 'config.ini')
        import configparser
        config = configparser.ConfigParser()
        config.read(config_file)
        
        settings = dict(config['Settings'])
        return jsonify({'success': True, 'config': settings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/config/save', methods=['POST'])
@login_required
def save_config():
    try:
        data = request.get_json()
        settings = data.get('settings', {})
        
        config_file = os.path.join(BASIC_FOLDER, 'config.ini')
        import configparser
        config = configparser.ConfigParser()
        config.read(config_file)
        
        for key, value in settings.items():
            config['Settings'][key] = str(value)
        
        with open(config_file, 'w') as f:
            config.write(f)
        
        return jsonify({'success': True, 'message': 'Configuration saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Campaign From Emails Management
@app.route('/api/campaign/from/list', methods=['GET'])
@login_required
def get_from_emails():
    try:
        from_file = os.path.join(BASIC_FOLDER, 'from.txt')
        if os.path.exists(from_file):
            with open(from_file, 'r') as f:
                count = sum(1 for line in f if line.strip() and '@' in line)
                return jsonify({'success': True, 'count': count})
        return jsonify({'success': True, 'count': 0})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/campaign/from/bulk', methods=['POST'])
@login_required
def bulk_add_from_emails():
    try:
        data = request.get_json()
        new_emails = data.get('emails', [])
        
        from_file = os.path.join(BASIC_FOLDER, 'from.txt')
        existing_emails = []
        
        if os.path.exists(from_file):
            with open(from_file, 'r') as f:
                existing_emails = [line.strip() for line in f if line.strip()]
        
        # Combine and remove duplicates
        all_emails = list(set(existing_emails + new_emails))
        duplicates = len(existing_emails) + len(new_emails) - len(all_emails)
        
        with open(from_file, 'w') as f:
            for email in all_emails:
                f.write(f"{email}\n")
        
        return jsonify({'success': True, 'added': len(all_emails) - len(existing_emails), 'duplicates': duplicates, 'total': len(all_emails)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/campaign/from/delete', methods=['POST'])
@login_required
def delete_from_email():
    try:
        data = request.get_json()
        index = data.get('index')
        
        from_file = os.path.join(BASIC_FOLDER, 'from.txt')
        with open(from_file, 'r') as f:
            emails = [line.strip() for line in f if line.strip()]
        
        if 0 <= index < len(emails):
            emails.pop(index)
        
        with open(from_file, 'w') as f:
            for email in emails:
                f.write(f"{email}\n")
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/campaign/from/clear', methods=['POST'])
@login_required
def clear_from_emails():
    try:
        from_file = os.path.join(BASIC_FOLDER, 'from.txt')
        with open(from_file, 'w') as f:
            f.write('')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Campaign Recipients Management
@app.route('/api/campaign/recipients/list', methods=['GET'])
@login_required
def get_recipients():
    try:
        recipients_file = os.path.join(BASIC_FOLDER, 'emailx.txt')
        if os.path.exists(recipients_file):
            with open(recipients_file, 'r') as f:
                count = sum(1 for line in f if line.strip() and '@' in line)
                return jsonify({'success': True, 'count': count})
        return jsonify({'success': True, 'count': 0})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/campaign/recipients/bulk', methods=['POST'])
@login_required
def bulk_add_recipients():
    try:
        data = request.get_json()
        new_emails = data.get('emails', [])
        
        recipients_file = os.path.join(BASIC_FOLDER, 'emailx.txt')
        existing_emails = []
        
        if os.path.exists(recipients_file):
            with open(recipients_file, 'r') as f:
                existing_emails = [line.strip() for line in f if line.strip()]
        
        # Combine and remove duplicates
        all_emails = list(set(existing_emails + new_emails))
        duplicates = len(existing_emails) + len(new_emails) - len(all_emails)
        
        with open(recipients_file, 'w') as f:
            for email in all_emails:
                f.write(f"{email}\n")
        
        return jsonify({'success': True, 'added': len(all_emails) - len(existing_emails), 'duplicates': duplicates, 'total': len(all_emails)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/campaign/recipients/delete', methods=['POST'])
@login_required
def delete_recipient():
    try:
        data = request.get_json()
        index = data.get('index')
        
        recipients_file = os.path.join(BASIC_FOLDER, 'emailx.txt')
        with open(recipients_file, 'r') as f:
            emails = [line.strip() for line in f if line.strip()]
        
        if 0 <= index < len(emails):
            emails.pop(index)
        
        with open(recipients_file, 'w') as f:
            for email in emails:
                f.write(f"{email}\n")
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/campaign/recipients/clear', methods=['POST'])
@login_required
def clear_recipients():
    try:
        recipients_file = os.path.join(BASIC_FOLDER, 'emailx.txt')
        with open(recipients_file, 'w') as f:
            f.write('')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/campaign/start', methods=['POST'])
@login_required
def start_campaign():
    global campaign_process, campaign_running, campaign_stats, campaign_logs
    
    if campaign_running:
        return jsonify({'success': False, 'error': 'Campaign already running'}), 400
    
    try:
        # Load configuration
        config_file = os.path.join(BASIC_FOLDER, 'config.ini')
        import configparser
        config = configparser.ConfigParser()
        config.read(config_file)
        
        # Load from emails
        from_file = os.path.join(BASIC_FOLDER, 'from.txt')
        if not os.path.exists(from_file):
            return jsonify({'success': False, 'error': 'No from emails configured'}), 400
        with open(from_file, 'r') as f:
            from_emails = [line.strip() for line in f if line.strip() and '@' in line]
        
        if not from_emails:
            return jsonify({'success': False, 'error': 'No from emails found'}), 400
        
        # Load recipients
        recipients_file = os.path.join(BASIC_FOLDER, 'emailx.txt')
        if not os.path.exists(recipients_file):
            return jsonify({'success': False, 'error': 'No recipients configured'}), 400
        with open(recipients_file, 'r') as f:
            recipients = [line.strip() for line in f if line.strip() and '@' in line]
        
        if not recipients:
            return jsonify({'success': False, 'error': 'No recipients found'}), 400
        
        # Load SMTP servers (only active ones)
        smtp_file = os.path.join(BASIC_FOLDER, 'smtp.txt')
        if not os.path.exists(smtp_file):
            return jsonify({'success': False, 'error': 'No SMTP servers configured'}), 400
        
        smtp_servers = []
        with open(smtp_file, 'r') as f:
            lines = f.readlines()[1:]  # Skip header
            for line in lines:
                if line.strip():
                    parts = line.strip().split(',')
                    if len(parts) >= 5:
                        smtp_servers.append({
                            'host': parts[0].strip(),
                            'port': parts[1].strip(),
                            'username': parts[2].strip(),
                            'password': parts[3].strip(),
                            'status': parts[4].strip() if len(parts) > 4 else 'inactive',
                            'sent': int(parts[5].strip()) if len(parts) > 5 else 0
                        })
        
        active_smtps = [s for s in smtp_servers if s['status'] == 'active']
        if not active_smtps:
            return jsonify({'success': False, 'error': 'No active SMTP servers found'}), 400
        
        # Load HTML template
        html_file = os.path.join(BASIC_FOLDER, config['Settings'].get('LETTERPATH', 'ma.html'))
        if not os.path.exists(html_file):
            return jsonify({'success': False, 'error': 'HTML template not found'}), 400
        with open(html_file, 'rb') as f:
            html_content = f.read().decode('utf-8')
        
        # Initialize campaign state
        campaign_stats = {
            'total_sent': 0,
            'total_failed': 0,
            'start_time': datetime.now().isoformat(),
            'status': 'running'
        }
        campaign_logs = []  # Clear previous logs
        campaign_running = True
        
        # Start the campaign in a separate thread (non-daemon so it continues after browser closes)
        thread = threading.Thread(
            target=run_campaign_background,
            args=(recipients, from_emails, smtp_servers, html_content, config['Settings'])
        )
        thread.daemon = False  # Allow campaign to continue running after browser closes
        thread.start()
        
        return jsonify({'success': True, 'message': f'Campaign started: {len(recipients)} recipients, {len(active_smtps)} active SMTPs'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/campaign/stop', methods=['POST'])
@login_required
def stop_campaign():
    global campaign_process, campaign_running, campaign_stats
    
    if not campaign_running:
        return jsonify({'success': False, 'error': 'No campaign running'}), 400
    
    try:
        if campaign_process:
            campaign_process.stop()
        
        campaign_running = False
        campaign_stats['status'] = 'stopped'
        
        socketio.emit('campaign_log', {'message': 'Campaign stopped by user', 'type': 'warning'})
        
        return jsonify({'success': True, 'message': 'Campaign stopped successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/campaign/stats', methods=['GET'])
@login_required
def get_campaign_stats():
    global campaign_logs
    with campaign_lock:
        return jsonify({
            'success': True,
            'stats': campaign_stats,
            'running': campaign_running,
            'logs': campaign_logs[-100:]  # Return last 100 logs
        })

@app.route('/api/campaign/status', methods=['GET'])
@login_required
def get_campaign_status():
    """Simple endpoint to check if campaign is running"""
    return jsonify({
        'success': True,
        'running': campaign_running,
        'stats': campaign_stats
    })

def run_campaign_background(recipients, from_emails, smtp_servers, html_content, config_settings):
    """Run campaign using campaign_sender module"""
    global campaign_process, campaign_running, campaign_stats, campaign_logs
    
    try:
        from campaign_sender import CampaignSender
        
        def campaign_callback(event):
            """Handle campaign events"""
            global campaign_logs, campaign_stats, campaign_running
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entry = {'time': timestamp, 'message': '', 'type': 'info'}
            
            if event['type'] == 'log':
                log_entry['message'] = event['message']
                log_entry['type'] = event['log_type']
                with campaign_lock:
                    campaign_logs.append(log_entry)
                    if len(campaign_logs) > 1000:  # Keep last 1000 logs
                        del campaign_logs[:-1000]
                socketio.emit('campaign_log', {'message': event['message'], 'type': event['log_type']})
                
            elif event['type'] == 'stats':
                with campaign_lock:
                    campaign_stats['total_sent'] = event['sent']
                    campaign_stats['total_failed'] = event['failed']
                socketio.emit('campaign_stats', {'sent': event['sent'], 'failed': event['failed']})
                
            elif event['type'] == 'from_count_update':
                # Update from email count in real-time
                socketio.emit('from_count_update', {
                    'total': event['total'],
                    'used': event['used'],
                    'remaining': event['remaining']
                })
                
            elif event['type'] == 'complete':
                # Update SMTP sent counts in smtp.txt
                update_smtp_sent_counts(event.get('smtp_stats', {}))
                with campaign_lock:
                    campaign_stats['status'] = 'completed'
                socketio.emit('campaign_complete', {'sent': event['sent'], 'failed': event['failed']})
        
        # Create campaign sender instance with from file path
        from_file_path = os.path.join(BASIC_FOLDER, 'from.txt')
        sender = CampaignSender(config_settings, campaign_callback, from_file_path)
        campaign_process = sender
        
        # Run campaign
        sender.send_campaign(
            recipients=recipients,
            from_emails=from_emails,
            smtp_servers=smtp_servers,
            html_content=html_content,
            subject=config_settings.get('subject', 'Important Message'),
            sender_name=config_settings.get('SENDERNAME', 'Support')
        )
        
    except Exception as e:
        error_msg = f'Campaign error: {str(e)}'
        with campaign_lock:
            campaign_logs.append({'time': datetime.now().strftime('%H:%M:%S'), 'message': error_msg, 'type': 'error'})
            campaign_stats['status'] = 'error'
        socketio.emit('campaign_log', {'message': error_msg, 'type': 'error'})
    finally:
        with campaign_lock:
            campaign_running = False
        campaign_process = None

def update_smtp_sent_counts(smtp_stats):
    """Update SMTP sent counts in smtp.txt"""
    try:
        smtp_file = os.path.join(BASIC_FOLDER, 'smtp.txt')
        if not os.path.exists(smtp_file):
            return
        
        with open(smtp_file, 'r') as f:
            lines = f.readlines()
        
        # Update sent counts
        with open(smtp_file, 'w') as f:
            f.write(lines[0])  # Header
            for line in lines[1:]:
                if line.strip():
                    parts = line.strip().split(',')
                    if len(parts) >= 4:
                        username = parts[2].strip()
                        current_sent = int(parts[5].strip()) if len(parts) > 5 else 0
                        new_sent = current_sent + smtp_stats.get(username, 0)
                        status = parts[4].strip() if len(parts) > 4 else 'inactive'
                        f.write(f"{parts[0]},{parts[1]},{parts[2]},{parts[3]},{status},{new_sent}\n")
    except Exception as e:
        print(f"Error updating SMTP counts: {e}")

# Email Monitoring API Endpoints
EMAIL_API_KEY = os.getenv('EMAIL_API_KEY', '@oldisgold@')

def verify_api_key():
    """Verify API key from request headers"""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False
    token = auth_header.replace('Bearer ', '')
    return token == EMAIL_API_KEY

@app.route('/api/initial_scan', methods=['POST'])
def initial_scan():
    """Receive all accounts and emails on startup"""
    if not verify_api_key():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        data = request.json
        with monitored_lock:
            monitored_data['total_accounts'] = data.get('total_accounts', 0)
            monitored_data['total_emails'] = data.get('total_emails', 0)
            monitored_data['last_update'] = datetime.now().isoformat()
            
            # Process accounts and add from_emails
            accounts_data = data.get('accounts', [])
            added_count = 0
            updated_count = 0
            skipped_count = 0
            
            for account in accounts_data:
                account_name = account.get('account_name')
                monitored_data['accounts'][account_name] = {
                    'from_emails': account.get('from_emails', []),
                    'emails': account.get('emails', []),
                    'email_count': len(account.get('emails', [])),
                    'from_count': len(account.get('from_emails', [])),
                    'last_email': account['emails'][0]['date'] if account.get('emails') else None
                }
                
                # Add from_emails to system (prevent duplicates, activate if inactive)
                for from_email in account.get('from_emails', []):
                    result = add_or_update_from_email(from_email, 'active')
                    if result == 'added':
                        added_count += 1
                    elif result == 'updated':
                        updated_count += 1
                    else:
                        skipped_count += 1
            
            # Calculate unique from emails across all accounts
            all_froms = set()
            for account in monitored_data['accounts'].values():
                all_froms.update(account['from_emails'])
            monitored_data['unique_froms'] = len(all_froms)
        
        print(f"✅ Initial scan: {monitored_data['total_accounts']} accounts, {monitored_data['total_emails']} emails")
        print(f"📧 From emails: {added_count} added, {updated_count} updated (inactive→active), {skipped_count} skipped")
        return jsonify({'status': 'success', 'added': added_count, 'updated': updated_count, 'skipped': skipped_count}), 200
    except Exception as e:
        print(f"❌ Error processing initial scan: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/new_email', methods=['POST'])
def new_email():
    """Receive real-time new email notifications"""
    if not verify_api_key():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        data = request.json
        account_name = data.get('account_name')
        from_email = data.get('from_email')
        subject = data.get('subject', '')
        
        # Check if this is a recheck response FIRST
        is_recheck_response = False
        
        if 'RECHECK_' in subject and recheck_campaign_running:
            # Extract unique_id from subject (format: RECHECK_xxxxxxxxxxxx)
            import re
            match = re.search(r'RECHECK_([a-f0-9]{12})', subject)
            if match:
                unique_id = f"RECHECK_{match.group(1)}"
                is_recheck_response = True
                
                try:
                    campaign_data = load_recheck_active()
                    if campaign_data:
                        froms_tested = campaign_data.get('froms_tested', {})
                        
                        # Find matching from email by unique_id (the from_email is the one being tested)
                        for test_email, test_data in froms_tested.items():
                            test_unique_id = test_data.get('unique_id', '')
                            if test_unique_id == unique_id:
                                # Only mark as working if not already marked (prevent duplicates)
                                if test_data.get('status') != 'working':
                                    test_data['status'] = 'working'
                                    test_data['delivered_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    test_data['response_from'] = from_email  # Track what email responded
                                    campaign_data['froms_tested'][test_email] = test_data
                                    save_recheck_active(campaign_data)
                                    
                                    # Count stats from UPDATED froms_tested dictionary
                                    updated_froms = campaign_data.get('froms_tested', {})
                                    working = sum(1 for d in updated_froms.values() if d.get('status') == 'working')
                                    failed = sum(1 for d in updated_froms.values() if d.get('status') == 'failed')
                                    pending = sum(1 for d in updated_froms.values() if d.get('status') == 'pending')
                                    
                                    # Emit Socket.IO event
                                    if recheck_campaign_callback:
                                        recheck_campaign_callback({
                                            'type': 'recheck_response_detected',
                                            'from_email': test_email,
                                            'working_count': working,
                                            'pending_count': pending,
                                            'failed_count': failed
                                        })
                                    
                                    print(f"✅ Recheck response detected: {test_email} (responded from {from_email}) - Total working: {working}")
                                break
                except Exception as e:
                    print(f"Error processing recheck response: {e}")
        
        if is_recheck_response:
            print(f"� Recheck response - NOT adding {from_email} to active froms automatically")
        else:
            print(f"�📧 New email received: {account_name} - {from_email} - {subject}")
        
        with monitored_lock:
            if account_name not in monitored_data['accounts']:
                monitored_data['accounts'][account_name] = {
                    'from_emails': [],
                    'emails': [],
                    'email_count': 0,
                    'from_count': 0,
                    'last_email': None
                }
            
            # Only add to active froms if this is NOT a recheck response
            if not is_recheck_response:
                # Add new from email if unique
                if from_email and from_email not in monitored_data['accounts'][account_name]['from_emails']:
                    monitored_data['accounts'][account_name]['from_emails'].append(from_email)
                    monitored_data['accounts'][account_name]['from_count'] += 1
                    
                    # Add to system (prevent duplicates, activate if inactive)
                    result = add_or_update_from_email(from_email, 'active')
                    if result == 'updated':
                        print(f"📧 From email {from_email} moved from inactive to active")
            
            # Add email to account
            email_data = {
                'from_email': from_email,
                'from_raw': data.get('from_raw'),
                'to': data.get('to'),
                'subject': subject,
                'date': data.get('date'),
                'timestamp': data.get('timestamp')
            }
            monitored_data['accounts'][account_name]['emails'].append(email_data)
            monitored_data['accounts'][account_name]['email_count'] += 1
            monitored_data['accounts'][account_name]['last_email'] = data.get('date')
            
            # Update totals
            monitored_data['total_emails'] += 1
            monitored_data['last_update'] = datetime.now().isoformat()
            
            # Recalculate unique froms
            all_froms = set()
            for account in monitored_data['accounts'].values():
                all_froms.update(account['from_emails'])
            monitored_data['unique_froms'] = len(all_froms)
        
        # Emit to connected clients via SocketIO (only if NOT recheck response)
        if not is_recheck_response:
            socketio.emit('new_monitored_email', {
                'account': account_name,
                'from': from_email,
                'subject': subject,
                'timestamp': data.get('timestamp')
            })
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f"❌ Error processing new email: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    """Optional: Status update every 10 checks"""
    if not verify_api_key():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        data = request.json
        print(f"💓 Heartbeat: {data.get('check_count')} checks, {data.get('new_emails_detected')} new emails")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/monitoring_summary', methods=['POST'])
def monitoring_summary():
    """Optional: Final stats when stopped"""
    if not verify_api_key():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        data = request.json
        print(f"📊 Monitoring Summary: {data.get('total_checks')} checks, {data.get('new_emails_detected')} new, {data.get('total_emails_tracked')} total")
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/monitored/froms', methods=['GET'])
@login_required
def get_monitored_froms():
    """Get monitored from emails for display in UI"""
    try:
        with monitored_lock:
            # Transform data for new UI with active/inactive status
            formatted_data = {}
            for account_name, account_data in monitored_data['accounts'].items():
                formatted_data[account_name] = {
                    'from_emails': [
                        {
                            'email': from_email,
                            'status': get_from_status(from_email),
                            'last_seen': account_data['last_email']
                        }
                        for from_email in account_data['from_emails']
                    ],
                    'email_count': account_data['email_count'],
                    'from_count': account_data['from_count'],
                    'last_email': account_data['last_email']
                }
            
            return jsonify(formatted_data)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Sending Campaign API endpoints
sending_recipients_file = os.path.join('Basic', 'sending_recipients.txt')
sending_settings_file = os.path.join('Basic', 'sending_config.ini')
sending_campaign_running = False
sending_campaign_thread = None
sending_campaign_callback = None

@app.route('/api/sending/toggle_from', methods=['POST'])
@login_required
def toggle_from_status():
    """Toggle from email between active and inactive"""
    try:
        data = request.json
        email = data.get('email')
        new_status = data.get('status')
        
        if not email or new_status not in ['active', 'inactive']:
            return jsonify({'success': False, 'error': 'Invalid parameters'}), 400
        
        # Save status to file
        if set_from_status(email, new_status):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save status'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sending/bulk_toggle', methods=['POST'])
@login_required
def bulk_toggle_from_status():
    """Toggle multiple from emails between active and inactive"""
    try:
        data = request.json
        emails = data.get('emails', [])
        new_status = data.get('status')
        
        if not emails or new_status not in ['active', 'inactive']:
            return jsonify({'success': False, 'error': 'Invalid parameters'}), 400
        
        # Load current status
        status_dict = load_from_status()
        
        # Update all emails
        for email in emails:
            status_dict[email] = new_status
        
        # Save
        if save_from_status(status_dict):
            return jsonify({'success': True, 'count': len(emails)})
        else:
            return jsonify({'success': False, 'error': 'Failed to save status'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sending/delete_froms', methods=['POST'])
@login_required
def delete_from_emails():
    """Delete selected from emails"""
    try:
        data = request.json
        emails = data.get('emails', [])
        
        if not emails:
            return jsonify({'success': False, 'error': 'No emails provided'}), 400
        
        # Load current status
        status_dict = load_from_status()
        
        # Remove emails
        deleted = 0
        for email in emails:
            if email in status_dict:
                del status_dict[email]
                deleted += 1
        
        # Save
        if save_from_status(status_dict):
            return jsonify({'success': True, 'deleted': deleted})
        else:
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sending/delete_all_froms', methods=['POST'])
@login_required
def delete_all_from_emails():
    """Delete all from emails with specified status"""
    try:
        data = request.json
        status_filter = data.get('status')
        
        if status_filter not in ['active', 'inactive']:
            return jsonify({'success': False, 'error': 'Invalid status'}), 400
        
        # Load current status
        status_dict = load_from_status()
        
        # Remove all with specified status
        emails_to_delete = [email for email, status in status_dict.items() if status == status_filter]
        for email in emails_to_delete:
            del status_dict[email]
        
        # Save
        if save_from_status(status_dict):
            return jsonify({'success': True, 'deleted': len(emails_to_delete)})
        else:
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sending/save_settings', methods=['POST'])
@login_required
def save_sending_settings():
    """Save sending campaign settings"""
    try:
        settings = request.json
        
        # Save to config file
        config = configparser.ConfigParser()
        if not config.has_section('sending'):
            config.add_section('sending')
        
        config.set('sending', 'from_source', settings.get('from_source', 'active'))
        config.set('sending', 'sender_name', settings.get('sender_name', ''))
        config.set('sending', 'subject', settings.get('subject', ''))
        config.set('sending', 'message', settings.get('message', ''))
        config.set('sending', 'sleep_time', str(settings.get('sleep_time', 1)))
        config.set('sending', 'threads', str(settings.get('threads', 1)))
        
        with open(sending_settings_file, 'w') as f:
            config.write(f)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sending/add_recipients', methods=['POST'])
@login_required
def add_sending_recipients():
    """Add recipients to sending campaign"""
    try:
        data = request.json
        new_recipients = data.get('recipients', [])
        
        # Read existing recipients
        existing = set()
        if os.path.exists(sending_recipients_file):
            with open(sending_recipients_file, 'r') as f:
                existing = set(line.strip() for line in f if line.strip())
        
        # Add new recipients (removing duplicates)
        before_count = len(existing)
        existing.update(new_recipients)
        after_count = len(existing)
        
        # Write back
        with open(sending_recipients_file, 'w') as f:
            for email in existing:
                f.write(f"{email}\n")
        
        return jsonify({
            'success': True,
            'added': after_count - before_count,
            'duplicates': len(new_recipients) - (after_count - before_count),
            'total': after_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sending/clear_recipients', methods=['POST'])
@login_required
def clear_sending_recipients():
    """Clear all recipients"""
    try:
        if os.path.exists(sending_recipients_file):
            with open(sending_recipients_file, 'w') as f:
                f.write('')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sending/recipients', methods=['GET'])
@login_required
def get_sending_recipients():
    """Get recipient count"""
    try:
        count = 0
        if os.path.exists(sending_recipients_file):
            with open(sending_recipients_file, 'r') as f:
                count = sum(1 for line in f if line.strip())
        return jsonify({'count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sending/start', methods=['POST'])
@login_required
def start_sending_campaign():
    """Start sending campaign"""
    global sending_campaign_running, sending_campaign_thread, sending_campaign_callback
    
    try:
        if sending_campaign_running:
            return jsonify({'success': False, 'message': 'Campaign already running'})
        
        # Validate we have recipients
        if not os.path.exists(sending_recipients_file):
            return jsonify({'success': False, 'message': 'No recipients added'})
        
        with open(sending_recipients_file, 'r') as f:
            recipients = [line.strip() for line in f if line.strip()]
        
        if not recipients:
            return jsonify({'success': False, 'message': 'No recipients added'})
        
        # Validate we have from emails
        with monitored_lock:
            total_froms = sum(len(acc['from_emails']) for acc in monitored_data['accounts'].values())
        
        if total_froms == 0:
            return jsonify({'success': False, 'message': 'No from emails available'})
        
        # Define callback to emit events from background thread
        def campaign_callback(event):
            try:
                event_type = event.get('type')
                print(f"[CALLBACK] Type: {event_type}, Message: {event.get('message', 'N/A')}")
                if event_type == 'sending_campaign_log':
                    socketio.emit('sending_campaign_log', {
                        'message': event['message'],
                        'log_type': event.get('log_type', 'info')
                    })
                    print(f"[CALLBACK] Emitted sending_campaign_log")
                elif event_type == 'sending_campaign_stats':
                    socketio.emit('sending_campaign_stats', {
                        'sent': event['sent']
                    })
                    print(f"[CALLBACK] Emitted sending_campaign_stats: {event['sent']}")
                elif event_type == 'sending_campaign_complete':
                    socketio.emit('sending_campaign_complete', {
                        'message': event['message']
                    })
                    print(f"[CALLBACK] Emitted sending_campaign_complete")
            except Exception as e:
                print(f"[CALLBACK ERROR] {e}")
                import traceback
                traceback.print_exc()
        
        # Store callback for thread access
        global sending_campaign_callback
        sending_campaign_callback = campaign_callback
        
        # Start campaign in background thread
        sending_campaign_running = True
        sending_campaign_thread = threading.Thread(target=run_sending_campaign, daemon=False)
        sending_campaign_thread.start()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sending/stop', methods=['POST'])
@login_required
def stop_sending_campaign():
    """Stop sending campaign"""
    global sending_campaign_running
    
    try:
        sending_campaign_running = False
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sending/status', methods=['GET'])
@login_required
def get_sending_status():
    """Get sending campaign status"""
    return jsonify({'running': sending_campaign_running})

# Recheck Froms Campaign API endpoints
recheck_config_file = os.path.join('Basic', 'recheck_config.json')
recheck_active_file = os.path.join('Basic', 'recheck_active.json')
recheck_campaign_running = False
recheck_campaign_thread = None
recheck_campaign_callback = None

def load_recheck_config():
    """Load recheck configuration"""
    try:
        if os.path.exists(recheck_config_file):
            with open(recheck_config_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading recheck config: {e}")
        return {}

def save_recheck_config(config):
    """Save recheck configuration"""
    try:
        with open(recheck_config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving recheck config: {e}")
        return False

def load_recheck_active():
    """Load active recheck campaign data"""
    try:
        if os.path.exists(recheck_active_file):
            with open(recheck_active_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading recheck active: {e}")
        return {}

def save_recheck_active(data):
    """Save active recheck campaign data"""
    try:
        with open(recheck_active_file, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving recheck active: {e}")
        return False

@app.route('/api/recheck/save_config', methods=['POST'])
@login_required
def save_recheck_configuration():
    """Save recheck configuration"""
    try:
        config = request.json
        thread_count = config.get('threads', 3)
        print(f"💾 Saving recheck config with {thread_count} threads")
        if save_recheck_config(config):
            return jsonify({'success': True, 'threads_saved': thread_count})
        return jsonify({'success': False, 'message': 'Failed to save configuration'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recheck/get_config', methods=['GET'])
@login_required
def get_recheck_configuration():
    """Get saved recheck configuration"""
    try:
        config = load_recheck_config()
        if not config:
            # Return default config with test recipients
            config = {
                'from_source': 'active',
                'threads': 3,
                'sender_name': 'Verification System',
                'subject': 'Verification {unique_id}',
                'recipients': [
                    'Footmen203@yahoo.com',
                    'Footmen404@yahoo.com',
                    'azoofoo2026@yahoo.com',
                    'azoofozora2026@yahoo.com',
                    'brb4mints@yahoo.com',
                    'atombrid2069@yahoo.com',
                    'micoland2026@yahoo.com',
                    'bravoeco2026@yahoo.com',
                    'laststand2026@yahoo.com',
                    'copermerv2026@yahoo.com'
                ],
                'message': ''
            }
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recheck/remove_duplicates', methods=['POST'])
@login_required
def remove_from_duplicates():
    """Remove duplicate from_emails before recheck"""
    try:
        removed = remove_duplicates_from_status()
        return jsonify({'success': True, 'removed': removed})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recheck/swap_results', methods=['POST'])
@login_required
def swap_recheck_results():
    """Move old active to inactive, new working to active"""
    try:
        status_dict = load_from_status()
        
        # Get current active emails (these will become inactive)
        old_active = [email for email, status in status_dict.items() if status == 'active']
        
        # Get working emails from recheck results (these will become active)
        campaign_data = load_recheck_active()
        if not campaign_data:
            return jsonify({'success': False, 'message': 'No recheck results found'}), 400
        
        froms_tested = campaign_data.get('froms_tested', {})
        working_emails = [email for email, data in froms_tested.items() if data.get('status') == 'working']
        
        if not working_emails:
            return jsonify({'success': False, 'message': 'No working emails found in results'}), 400
        
        # Step 1: Move ALL old active emails to inactive
        moved_to_inactive = 0
        for email in old_active:
            status_dict[email] = 'inactive'
            moved_to_inactive += 1
            print(f"📥 Moved to inactive: {email}")
        
        # Step 2: Move ALL working emails to active (remove from inactive if exists)
        moved_to_active = 0
        for email in working_emails:
            # Remove from any other status first to enforce single status rule
            if email in status_dict and status_dict[email] != 'active':
                print(f"🔄 Removing {email} from {status_dict[email]} before making active")
            
            status_dict[email] = 'active'
            moved_to_active += 1
            print(f"📤 Moved to active: {email}")
        
        # Step 3: Final cleanup - ensure no duplicates (each email has ONE status)
        # Already handled by using dict, but verify counts
        active_count = sum(1 for s in status_dict.values() if s == 'active')
        inactive_count = sum(1 for s in status_dict.values() if s == 'inactive')
        
        save_from_status(status_dict)
        
        print(f"✅ Swap complete: {moved_to_inactive} moved to inactive, {moved_to_active} moved to active")
        print(f"📊 Final counts: {active_count} active, {inactive_count} inactive")
        
        return jsonify({
            'success': True,
            'moved_to_inactive': moved_to_inactive,
            'moved_to_active': moved_to_active,
            'final_active_count': active_count,
            'final_inactive_count': inactive_count
        })
    except Exception as e:
        print(f"❌ Error swapping results: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recheck/start', methods=['POST'])
@login_required
def start_recheck_campaign():
    """Start recheck campaign"""
    global recheck_campaign_running, recheck_campaign_thread, recheck_campaign_callback
    
    try:
        if recheck_campaign_running:
            return jsonify({'success': False, 'message': 'Recheck campaign already running'})
        
        # Remove duplicates before starting
        removed = remove_duplicates_from_status()
        if removed > 0:
            print(f"🧹 Removed {removed} duplicate from_emails before recheck")
        
        # Load config
        config = load_recheck_config()
        if not config:
            return jsonify({'success': False, 'message': 'No configuration found. Please save configuration first.'}), 400
        
        # Validate recipients
        recipients = config.get('recipients', [])
        if not recipients:
            return jsonify({'success': False, 'message': 'No test recipients configured'}), 400
        
        # Get from emails based on source
        from_source = config.get('from_source', 'active')
        with monitored_lock:
            all_from_emails = []
            for account_data in monitored_data['accounts'].values():
                all_from_emails.extend(account_data['from_emails'])
        
        # Filter based on from_source
        filtered_from_emails = []
        for from_email in all_from_emails:
            status = get_from_status(from_email)
            if from_source == 'active' and status == 'active':
                filtered_from_emails.append(from_email)
            elif from_source == 'inactive' and status == 'inactive':
                filtered_from_emails.append(from_email)
            elif from_source == 'all':
                filtered_from_emails.append(from_email)
        
        if not filtered_from_emails:
            return jsonify({'success': False, 'message': f'No {from_source} from emails available'}), 400
        
        # Define callback for Socket.IO events
        def campaign_callback(event):
            try:
                event_type = event.get('type')
                if event_type == 'recheck_progress':
                    socketio.emit('recheck_progress', {
                        'sent': event['sent'],
                        'total': event['total']
                    })
                elif event_type == 'recheck_log':
                    socketio.emit('recheck_log', {
                        'message': event['message'],
                        'log_type': event.get('log_type', 'info')
                    })
                elif event_type == 'recheck_sending_complete':
                    socketio.emit('recheck_sending_complete', {})
                elif event_type == 'recheck_response_detected':
                    socketio.emit('recheck_response_detected', {
                        'from_email': event['from_email'],
                        'working_count': event['working_count'],
                        'pending_count': event['pending_count'],
                        'failed_count': event['failed_count']
                    })
            except Exception as e:
                print(f"[RECHECK CALLBACK ERROR] {e}")
        
        # Store callback
        recheck_campaign_callback = campaign_callback
        
        # Initialize campaign data
        import uuid
        campaign_id = f"recheck_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        campaign_data = {
            'campaign_id': campaign_id,
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'from_source': from_source,
            'froms_tested': {},
            'config': config
        }
        
        # Initialize all froms as pending
        for from_email in filtered_from_emails:
            campaign_data['froms_tested'][from_email] = {
                'status': 'pending',
                'unique_id': f"RECHECK_{uuid.uuid4().hex[:12]}",
                'sent_at': None,
                'delivered_at': None
            }
        
        save_recheck_active(campaign_data)
        
        # Start campaign thread
        recheck_campaign_running = True
        recheck_campaign_thread = threading.Thread(target=run_recheck_campaign, daemon=False)
        recheck_campaign_thread.start()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recheck/stop', methods=['POST'])
@login_required
def stop_recheck_campaign():
    """Stop recheck campaign"""
    global recheck_campaign_running
    
    try:
        recheck_campaign_running = False
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recheck/status', methods=['GET'])
@login_required
def get_recheck_status():
    """Get recheck campaign status"""
    return jsonify({'running': recheck_campaign_running})

@app.route('/api/recheck/results', methods=['GET'])
@login_required
def get_recheck_results():
    """Get recheck campaign results"""
    try:
        campaign_data = load_recheck_active()
        if not campaign_data:
            return jsonify({'success': False, 'message': 'No active campaign'}), 404
        
        froms_tested = campaign_data.get('froms_tested', {})
        
        working = []
        failed = []
        pending = []
        
        for email, data in froms_tested.items():
            from_data = {
                'email': email,
                'sent_at': data.get('sent_at'),
                'delivered_at': data.get('delivered_at'),
                'unique_id': data.get('unique_id')
            }
            
            if data.get('status') == 'working':
                working.append(from_data)
            elif data.get('status') == 'failed':
                failed.append(from_data)
            else:
                pending.append(from_data)
        
        return jsonify({
            'success': True,
            'results': {
                'working': working,
                'failed': failed,
                'pending': pending
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recheck/apply_results', methods=['POST'])
@login_required
def apply_recheck_results():
    """Apply bulk status changes from recheck results"""
    try:
        data = request.json
        action = data.get('action')
        
        campaign_data = load_recheck_active()
        if not campaign_data:
            return jsonify({'success': False, 'message': 'No active campaign'}), 404
        
        froms_tested = campaign_data.get('froms_tested', {})
        
        if action == 'swap':
            # Move working to active, failed to inactive
            active_count = 0
            inactive_count = 0
            
            for email, from_data in froms_tested.items():
                if from_data.get('status') == 'working':
                    set_from_status(email, 'active')
                    active_count += 1
                elif from_data.get('status') == 'failed':
                    set_from_status(email, 'inactive')
                    inactive_count += 1
            
            return jsonify({
                'success': True,
                'active_count': active_count,
                'inactive_count': inactive_count
            })
        
        elif action == 'bulk':
            # Bulk move specific emails
            emails = data.get('emails', [])
            status = data.get('status', 'active')
            
            count = 0
            for email in emails:
                if set_from_status(email, status):
                    count += 1
            
            return jsonify({
                'success': True,
                'count': count
            })
        
        return jsonify({'success': False, 'message': 'Invalid action'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def run_recheck_campaign():
    """Background thread for recheck campaign with multi-threading support"""
    global recheck_campaign_running, recheck_campaign_callback
    
    print(f"[RECHECK THREAD START] Callback available: {recheck_campaign_callback is not None}")
    
    def emit_log(message, log_type='info'):
        """Helper to emit logs via callback"""
        print(f"[RECHECK LOG] {message}")
        if recheck_campaign_callback:
            recheck_campaign_callback({
                'type': 'recheck_log',
                'message': message,
                'log_type': log_type
            })
    
    def emit_progress(sent, total):
        """Helper to emit progress"""
        if recheck_campaign_callback:
            recheck_campaign_callback({
                'type': 'recheck_progress',
                'sent': sent,
                'total': total
            })
    
    def send_test_email(from_email, from_data, smtp_server, config, recipients):
        """Worker function to send test email from one from_email"""
        unique_id = from_data['unique_id']
        
        # Check if SMTP has too many failures or auth rejections
        if smtp_server.get('failures', 0) >= 5:
            emit_log(f'⚠️ Skipping {smtp_server["host"]} (connection failures)', 'warning')
            return (from_email, False, from_data, smtp_server, True)
        
        if smtp_server.get('auth_failures', 0) >= 3:
            emit_log(f'⚠️ Skipping {smtp_server["host"]} (rejects fake senders)', 'warning')
            return (from_email, False, from_data, smtp_server, True)
            return (from_email, False, from_data, smtp_server, True)  # Return smtp_failed=True
        
        # Prepare message
        subject = config.get('subject', 'Verification {unique_id}')
        subject = subject.replace('{unique_id}', unique_id).replace('{from_email}', from_email).replace('{timestamp}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        message_body = config.get('message', '')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        emit_log(f'🔄 Processing {from_email} via {smtp_server["host"]}...', 'info')
        
        # Send to all test recipients
        success = False
        smtp_error = False
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            import email.utils
            
            for recipient in recipients:
                try:
                    # Replace variables in message
                    msg_html = message_body.replace('{from_email}', from_email)
                    msg_html = msg_html.replace('{unique_id}', unique_id)
                    msg_html = msg_html.replace('{timestamp}', timestamp)
                    msg_html = msg_html.replace('{recipient}', recipient)
                    
                    msg = MIMEMultipart("alternative")
                    sender_name = config.get('sender_name', 'Verification System')
                    msg['From'] = f'{sender_name} <{from_email}>' if sender_name else from_email
                    msg['To'] = recipient
                    msg['Date'] = email.utils.formatdate(localtime=True)
                    msg['Subject'] = subject
                    msg["Message-ID"] = f"<{unique_id}@recheck.portal>"
                    
                    msg.attach(MIMEText(msg_html, 'html'))
                    
                    with smtplib.SMTP(smtp_server['host'], int(smtp_server['port']), timeout=30) as server:
                        server.starttls()
                        server.login(smtp_server['username'], smtp_server['password'])
                        server.send_message(msg)
                    
                    success = True
                    # Reset failure count on success
                    smtp_server['failures'] = 0
                    
                except Exception as e:
                    emit_log(f'⚠️ Failed to {recipient}: {str(e)[:80]}', 'warning')
                    continue
            
            return (from_email, success, from_data, smtp_server, False)
            
        except Exception as e:
            error_str = str(e).lower()
            smtp_error = True
            
            # Check if it's an AUTH/SENDER rejection error (SMTP doesn't allow fake froms)
            is_auth_error = any(x in error_str for x in [
                'mail from must equal',
                'sender address rejected',
                'not permitted',
                'authenticated sender',
                'must match'
            ])
            
            if is_auth_error:
                smtp_server['auth_failures'] = smtp_server.get('auth_failures', 0) + 1
                
                if smtp_server['auth_failures'] >= 3:
                    emit_log(f'❌ SMTP {smtp_server["host"]} rejects fake senders (3 auth errors) - MARKING AS INACTIVE', 'error')
                    smtp_server['failures'] = 5  # Force immediate deactivation
                else:
                    emit_log(f'⚠️ {smtp_server["host"]} auth error ({smtp_server["auth_failures"]}/3): {str(e)[:80]}', 'warning')
            else:
                # Regular connection/timeout errors
                smtp_server['failures'] = smtp_server.get('failures', 0) + 1
                
                if smtp_server['failures'] >= 5:
                    emit_log(f'❌ SMTP {smtp_server["host"]} FAILED 5 times - MARKING AS INACTIVE', 'error')
                else:
                    emit_log(f'❌ SMTP error for {from_email} ({smtp_server["failures"]}/5 failures): {str(e)[:100]}', 'error')
            
            import traceback
            print(f"[RECHECK ERROR] {traceback.format_exc()}")
            return (from_email, False, from_data, smtp_server, True)
    
    try:
        emit_log('🚀 Starting recheck campaign...', 'info')
        
        # Load campaign data
        campaign_data = load_recheck_active()
        if not campaign_data:
            emit_log('❌ No campaign data found', 'error')
            return
        
        config = campaign_data.get('config', {})
        froms_tested = campaign_data.get('froms_tested', {})
        recipients = config.get('recipients', [])
        
        emit_log(f'📋 Testing {len(froms_tested)} from addresses', 'info')
        emit_log(f'📧 Sending to {len(recipients)} test recipients', 'info')
        
        # Load ACTIVE SMTP servers from /smtp page database
        smtp_file = os.path.join('Basic', 'smtp.txt')
        smtp_servers = []
        
        if os.path.exists(smtp_file):
            with open(smtp_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[1:], 1):  # Skip header
                    if line.strip():
                        parts = line.strip().split(',')
                        if len(parts) >= 5 and parts[4].strip() == 'active':
                            smtp_servers.append({
                                'id': i,
                                'host': parts[0].strip(),
                                'port': parts[1].strip(),
                                'username': parts[2].strip(),
                                'password': parts[3].strip(),
                                'status': 'active',
                                'sent': int(parts[5]) if len(parts) > 5 else 0,
                                'failures': 0,
                                'auth_failures': 0  # Track auth/sender rejections
                            })
        
        if not smtp_servers:
            emit_log('❌ No ACTIVE SMTPs found. Please activate SMTPs at /smtp page', 'error')
            recheck_campaign_running = False
            return
        
        emit_log(f'✅ Loaded {len(smtp_servers)} ACTIVE SMTPs from /smtp page', 'success')
        
        # Get thread count from config (default 3)
        thread_count = config.get('threads', 3)
        emit_log(f'📮 Using {len(smtp_servers)} SMTP servers with {thread_count} threads', 'info')
        
        # Send test emails using ThreadPoolExecutor
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        sent_count = 0
        total_count = len(froms_tested)
        smtp_index = 0
        smtp_lock = threading.Lock()
        count_lock = threading.Lock()
        
        def get_next_smtp():
            """Thread-safe SMTP round-robin - skip failed and auth-rejected SMTPs"""
            nonlocal smtp_index
            with smtp_lock:
                # Try to find a working SMTP (not failed and doesn't reject auth)
                attempts = 0
                while attempts < len(smtp_servers):
                    smtp = smtp_servers[smtp_index]
                    smtp_index = (smtp_index + 1) % len(smtp_servers)
                    
                    # Skip if failed 5 times OR auth rejected 3 times
                    if smtp.get('failures', 0) < 5 and smtp.get('auth_failures', 0) < 3:
                        return smtp
                    
                    attempts += 1
                
                # All SMTPs failed - return first one anyway (will be skipped in send function)
                emit_log('⚠️ All SMTPs have been marked as failed! Check /smtp page', 'error')
                return smtp_servers[0]
        
        # Prepare tasks
        tasks = []
        for from_email, from_data in froms_tested.items():
            smtp_server = get_next_smtp()
            tasks.append((from_email, from_data, smtp_server))
        
        # Execute with thread pool
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = {}
            for from_email, from_data, smtp_server in tasks:
                if not recheck_campaign_running:
                    break
                future = executor.submit(send_test_email, from_email, from_data, smtp_server, config, recipients)
                futures[future] = from_email
            
            # Process completed tasks
            for future in as_completed(futures):
                if not recheck_campaign_running:
                    emit_log('⚠️ Campaign stopped by user', 'warning')
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                try:
                    from_email, success, from_data, smtp_server, smtp_failed = future.result()
                    
                    # Check if SMTP failed and needs to be marked inactive
                    if smtp_failed and smtp_server.get('failures', 0) >= 5:
                        # Mark SMTP as inactive in smtp.txt (synced with /smtp page)
                        smtp_file = os.path.join('Basic', 'smtp.txt')
                        if os.path.exists(smtp_file):
                            lines = []
                            updated = False
                            with open(smtp_file, 'r') as f:
                                for idx, line in enumerate(f):
                                    if idx == 0:  # Keep header
                                        lines.append(line)
                                        continue
                                    
                                    parts = line.strip().split(',')
                                    if len(parts) >= 5 and parts[0].strip() == smtp_server['host']:
                                        # Mark as inactive
                                        parts[4] = 'inactive'
                                        lines.append(','.join(parts) + '\n')
                                        emit_log(f'🚫 Marked {smtp_server["host"]} as INACTIVE (visible on /smtp page)', 'warning')
                                        updated = True
                                    else:
                                        lines.append(line)
                            
                            if updated:
                                with open(smtp_file, 'w') as f:
                                    f.writelines(lines)
                    
                    with count_lock:
                        if success:
                            # Update status
                            from_data['sent_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            campaign_data['froms_tested'][from_email] = from_data
                            save_recheck_active(campaign_data)
                            
                            sent_count += 1
                            emit_log(f'📤 Sent test from {from_email} ({sent_count}/{total_count})', 'info')
                            emit_progress(sent_count, total_count)
                        else:
                            emit_log(f'❌ All recipients failed for {from_email}', 'error')
                            sent_count += 1
                            emit_progress(sent_count, total_count)
                
                except Exception as e:
                    with count_lock:
                        sent_count += 1
                        emit_progress(sent_count, total_count)
                    emit_log(f'❌ Task error: {str(e)[:100]}', 'error')
        
        # Campaign summary
        emit_log(f'✅ Sending complete! Sent {sent_count}/{total_count} test emails', 'success')
        
        if recheck_campaign_callback:
            recheck_campaign_callback({'type': 'recheck_sending_complete'})
        
        # Wait 5 minutes for responses (monitored by countdown timer on frontend)
        emit_log('⏱️ Starting 5-minute countdown for responses...', 'info')
        
        # Mark remaining as failed after campaign ends (will be updated by API responses)
        
    except Exception as e:
        emit_log(f'💥 CRITICAL ERROR: {str(e)}', 'error')
        import traceback
        emit_log(f'📋 Traceback: {traceback.format_exc()[:500]}', 'error')
    finally:
        recheck_campaign_running = False

def run_sending_campaign():
    """Background thread for sending campaign"""
    global sending_campaign_running, sending_campaign_callback
    
    print(f"[THREAD START] run_sending_campaign started. Callback available: {sending_campaign_callback is not None}")
    
    def emit_log(message, log_type='info'):
        """Helper to emit logs via callback"""
        print(f"[EMIT_LOG] {message}")
        if sending_campaign_callback:
            sending_campaign_callback({
                'type': 'sending_campaign_log',
                'message': message,
                'log_type': log_type
            })
        else:
            print(f"[EMIT_LOG WARNING] No callback available!")
    
    def emit_stats(sent):
        """Helper to emit stats via callback"""
        if sending_campaign_callback:
            sending_campaign_callback({
                'type': 'sending_campaign_stats',
                'sent': sent
            })
    
    try:
        emit_log('🚀 Initializing campaign...', 'info')
        
        # Load settings
        config = configparser.ConfigParser()
        if os.path.exists(sending_settings_file):
            config.read(sending_settings_file)
        
        from_source = config.get('sending', 'from_source', fallback='active')
        sender_name = config.get('sending', 'sender_name', fallback='')
        subject = config.get('sending', 'subject', fallback='No Subject')
        message = config.get('sending', 'message', fallback='')
        sleep_time = config.getint('sending', 'sleep_time', fallback=1)
        threads = config.getint('sending', 'threads', fallback=1)
        
        emit_log(f'📋 Settings: source={from_source}, subject="{subject}"', 'info')
        
        # Load recipients
        if not os.path.exists(sending_recipients_file):
            emit_log('❌ No recipients file found. Add recipients in Recipients tab.', 'error')
            sending_campaign_running = False
            return
            
        with open(sending_recipients_file, 'r') as f:
            recipients = [line.strip() for line in f if line.strip()]
        
        if not recipients:
            emit_log('❌ No recipients found. Add recipients in Recipients tab.', 'error')
            sending_campaign_running = False
            return
        
        emit_log(f'📧 Loaded {len(recipients)} recipient(s): {recipients[0]}', 'info')
        
        # Get from emails based on source and filter by status
        with monitored_lock:
            all_from_emails = []
            for account_data in monitored_data['accounts'].values():
                all_from_emails.extend(account_data['from_emails'])
        
        emit_log(f'📬 Found {len(all_from_emails)} total from emails', 'info')
        
        # Filter based on from_source setting
        filtered_from_emails = []
        for from_email in all_from_emails:
            status = get_from_status(from_email)
            if from_source == 'active' and status == 'active':
                filtered_from_emails.append(from_email)
            elif from_source == 'inactive' and status == 'inactive':
                filtered_from_emails.append(from_email)
            elif from_source == 'all':
                filtered_from_emails.append(from_email)
        
        if not filtered_from_emails:
            emit_log(f'❌ No {from_source} from emails available. Check Active/Inactive Froms tabs.', 'error')
            sending_campaign_running = False
            return
        
        emit_log(f'✅ Using {len(filtered_from_emails)} {from_source} from(s): {filtered_from_emails[0]}', 'success')
        
        # Load SMTP servers from Check Froms (only active ones)
        smtp_file = os.path.join('Basic', 'smtp.txt')
        smtp_servers = []
        if os.path.exists(smtp_file):
            with open(smtp_file, 'r') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 5:  # host,port,username,password,status
                        if parts[4] == 'active':  # Only use active SMTPs
                            smtp_servers.append({
                                'host': parts[0],
                                'port': parts[1],
                                'username': parts[2],
                                'password': parts[3],
                                'status': parts[4]
                            })
                    elif len(parts) >= 4:  # Old format without status
                        smtp_servers.append({
                            'host': parts[0],
                            'port': parts[1],
                            'username': parts[2],
                            'password': parts[3],
                            'status': 'active'
                        })
        
        if not smtp_servers:
            emit_log('❌ No ACTIVE SMTP servers. Go to Check Froms → SMTP tab and add servers.', 'error')
            sending_campaign_running = False
            return
        
        emit_log(f'📮 Loaded {len(smtp_servers)} ACTIVE SMTP(s): {smtp_servers[0]["host"]}', 'info')
        emit_log(f'🎯 Starting: {len(filtered_from_emails)} froms → {len(recipients)} recipients', 'info')
        
        # Round-robin sending
        sent_count = 0
        from_index = 0
        smtp_index = 0
        
        for recipient in recipients:
            if not sending_campaign_running:
                emit_log('⚠️ Campaign stopped by user', 'warning')
                break
            
            # Get next from email (round-robin)
            current_from = filtered_from_emails[from_index]
            from_index = (from_index + 1) % len(filtered_from_emails)
            
            # Get next SMTP server (round-robin)
            smtp_server = smtp_servers[smtp_index]
            smtp_index = (smtp_index + 1) % len(smtp_servers)
            
            # Actually send email using SMTP
            try:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                import email.utils
                import uuid
                
                emit_log(f'📤 Sending to {recipient} from {current_from} via {smtp_server["host"]}...', 'info')
                
                msg = MIMEMultipart("alternative")
                msg['From'] = f'{sender_name} <{current_from}>' if sender_name else current_from
                msg['To'] = recipient
                msg['Date'] = email.utils.formatdate(localtime=True)
                msg['Subject'] = subject
                msg["Message-ID"] = f"<{str(uuid.uuid4())}@sending.portal>"
                
                # Attach message
                msg.attach(MIMEText(message, 'html'))
                
                # Connect and send
                with smtplib.SMTP(smtp_server['host'], int(smtp_server['port']), timeout=30) as server:
                    server.starttls()
                    server.login(smtp_server['username'], smtp_server['password'])
                    server.send_message(msg)
                
                sent_count += 1
                emit_log(f'✉️ SUCCESS! Sent #{sent_count} to {recipient} from {current_from}', 'success')
                emit_stats(sent_count)
                
            except Exception as e:
                emit_log(f'❌ FAILED to {recipient}: {str(e)[:100]}', 'error')
            
            time.sleep(sleep_time)
        
        if sending_campaign_callback:
            sending_campaign_callback({
                'type': 'sending_campaign_complete',
                'message': f'✅ Campaign completed! Sent {sent_count}/{len(recipients)} emails'
            })
        
    except Exception as e:
        emit_log(f'💥 CRITICAL ERROR: {str(e)}', 'error')
        import traceback
        emit_log(f'📋 Traceback: {traceback.format_exc()[:500]}', 'error')
    finally:
        sending_campaign_running = False

# WebSocket events
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connection_response', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
