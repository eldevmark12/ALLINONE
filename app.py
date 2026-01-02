import os
import json
import threading
import subprocess
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
