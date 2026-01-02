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
                            servers.append({
                                'id': i,
                                'host': parts[0].strip(),
                                'port': parts[1].strip(),
                                'username': parts[2].strip(),
                                'password': parts[3].strip()
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
            f.write('host,port,username,password\n')
            for server in servers:
                f.write(f"{server['host']},{server['port']},{server['username']},{server['password']}\n")
        
        return jsonify({'success': True, 'message': 'SMTP servers saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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

@app.route('/api/campaign/start', methods=['POST'])
@login_required
def start_campaign():
    global campaign_process, campaign_running, campaign_stats
    
    if campaign_running:
        return jsonify({'success': False, 'error': 'Campaign already running'}), 400
    
    try:
        campaign_stats = {
            'total_sent': 0,
            'total_failed': 0,
            'start_time': datetime.now().isoformat(),
            'status': 'running'
        }
        
        # Start the campaign in a separate thread
        thread = threading.Thread(target=run_campaign_background)
        thread.daemon = True
        thread.start()
        
        campaign_running = True
        
        return jsonify({'success': True, 'message': 'Campaign started successfully'})
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
            campaign_process.terminate()
            campaign_process = None
        
        campaign_running = False
        campaign_stats['status'] = 'stopped'
        
        socketio.emit('campaign_stopped', campaign_stats)
        
        return jsonify({'success': True, 'message': 'Campaign stopped successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/campaign/stats', methods=['GET'])
@login_required
def get_campaign_stats():
    return jsonify({
        'success': True,
        'stats': campaign_stats,
        'running': campaign_running
    })

def run_campaign_background():
    """Run the mainnotall.py script in background"""
    global campaign_process, campaign_running, campaign_stats
    
    try:
        script_path = os.path.join(BASIC_FOLDER, 'mainnotall.py')
        
        # Change to Basic directory to run the script
        os.chdir(BASIC_FOLDER)
        
        campaign_process = subprocess.Popen(
            ['python', 'mainnotall.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Monitor the process output
        for line in campaign_process.stdout:
            if line:
                # Parse output and emit via websocket
                socketio.emit('campaign_log', {'message': line.strip()})
                
                # Update stats (you can parse the output for specific info)
                if 'successfully' in line.lower():
                    campaign_stats['total_sent'] += 1
                elif 'failed' in line.lower() or 'error' in line.lower():
                    campaign_stats['total_failed'] += 1
                
                socketio.emit('campaign_stats', campaign_stats)
        
        campaign_process.wait()
        
    except Exception as e:
        socketio.emit('campaign_error', {'error': str(e)})
    finally:
        campaign_running = False
        campaign_stats['status'] = 'completed'
        socketio.emit('campaign_completed', campaign_stats)
        os.chdir('..')  # Return to root directory

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
