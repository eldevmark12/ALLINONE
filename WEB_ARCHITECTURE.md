# 🌐 Web-Based Email Platform Architecture

## 🎯 Core Requirement
**Background Persistence**: Campaigns must continue running even when user closes the browser. When they reopen, they see live progress.

## 📊 Original Windows GUI System Analysis

### Fake-client/GUI-Mailer (3003 lines)
**What it does:**
1. **Bulk Email Sending** - Send personalized emails to thousands of recipients
2. **SMTP Rotation** - Thread-safe rotation through SMTP pool with auto-disable on failure
3. **FROM Address Management** - Rotate sender addresses, verify via IMAP
4. **Email Verification** - Send test emails, check IMAP inbox to verify delivery
5. **Inbox Monitoring** - Monitor Thunderbird/IMAP for new emails, collect FROM addresses
6. **Template Personalization** - Variables: {RECIPIENT}, {NAME}, {DATE}, {RAND:1-100}
7. **Multi-threaded** - Concurrent sending with configurable thread count
8. **Auto-Recovery** - VPN drop detection, SMTP failure handling, connection retry
9. **Real-time Stats** - Live progress, success/failure counters, SMTP health

**Key Components:**
- `sending_manager.py` - Bulk sending with sender rotation (251 lines)
- `smtp_manager.py` - SMTP pool with failure tracking (124 lines)
- `verification_manager.py` - Email verification via IMAP (589 lines)
- `inbox_monitor.py` - Monitor IMAP for new messages (334 lines)
- `config_manager.py` - Persistent configuration

### Fake-client/SMTP-Validator (782 lines)
**What it does:**
1. **SMTP Testing** - Test multiple SMTP servers in parallel
2. **Delivery Verification** - Send test emails, verify via IMAP which were delivered
3. **Tracking System** - Unique tracking IDs match sent → delivered
4. **Multi-folder Check** - Check INBOX, Junk, Spam
5. **Export Results** - Extract working vs failed SMTPs

**Key Feature:** Background verification runs independently, user can check results later

## 🏗️ Web Platform Architecture

### Technology Stack

**Backend:**
- **Flask 3.0** - Web API framework
- **Celery 5.4** - Background task queue (THE KEY COMPONENT)
- **Redis 7** - Message broker for Celery + real-time pub/sub
- **PostgreSQL 15** - Persistent database
- **Flask-SocketIO** - Real-time WebSocket updates (when user is connected)
- **SQLAlchemy** - ORM

**Frontend:**
- **React 18** - Modern UI framework
- **Socket.IO Client** - Real-time updates
- **Recharts** - Live statistics visualization
- **Axios** - API communication

**Deployment:**
- **Render.com** - Hosting platform
- **Web Service** - Flask API ($7/month or free with spin-down)
- **Worker Service** - Celery background workers ($7/month)
- **Redis** - Task queue & pub/sub ($10/month)
- **PostgreSQL** - Database ($7/month or free 90-day)

### Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER BROWSER                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         React Dashboard (Frontend)                    │  │
│  │  - Campaign Manager (Start/Stop/Pause)               │  │
│  │  - SMTP Pool Viewer (Health Status)                  │  │
│  │  - Live Statistics (WebSocket Updates)               │  │
│  │  - FROM Address Verifier                             │  │
│  │  - Template Editor                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│         ↕️ HTTP API + WebSocket                             │
└─────────────────────────────────────────────────────────────┘
                            ↕️
┌─────────────────────────────────────────────────────────────┐
│                     FLASK WEB SERVICE                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Flask API (app.py)                           │  │
│  │  - Campaign CRUD endpoints                            │  │
│  │  - SMTP management                                    │  │
│  │  - Real-time status endpoints                         │  │
│  │  - WebSocket event handlers                           │  │
│  │  - Queue campaign tasks to Celery                     │  │
│  └──────────────────────────────────────────────────────┘  │
│         ↕️ Queue tasks via Redis                            │
└─────────────────────────────────────────────────────────────┘
                            ↕️
┌─────────────────────────────────────────────────────────────┐
│                   CELERY WORKER SERVICE                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │    Background Tasks (tasks/campaign_tasks.py)        │  │
│  │                                                       │  │
│  │  @celery.task                                         │  │
│  │  def bulk_send_campaign(campaign_id):                 │  │
│  │      while campaign.running:                          │  │
│  │          smtp = get_next_smtp()  # Rotation           │  │
│  │          from_addr = get_next_from()  # Rotation      │  │
│  │          recipient = get_next_recipient()             │  │
│  │          send_email(smtp, from_addr, recipient)       │  │
│  │          update_stats_in_db()                         │  │
│  │          emit_socketio_update()  # If user watching   │  │
│  │          time.sleep(sleep_interval)                   │  │
│  │                                                       │  │
│  │  @celery.task                                         │  │
│  │  def verify_from_addresses(verification_id):          │  │
│  │      # Send test emails, monitor IMAP                 │  │
│  │                                                       │  │
│  │  @celery.task                                         │  │
│  │  def monitor_inbox_continuous(monitor_id):            │  │
│  │      # Continuous IMAP monitoring                     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
          ↕️ Read/Write                ↕️ Pub/Sub
┌──────────────────────┐    ┌──────────────────────────────┐
│   POSTGRESQL DB      │    │       REDIS                  │
│  - campaigns         │    │  - Task Queue (Celery)       │
│  - smtp_servers      │    │  - Campaign State Cache      │
│  - from_addresses    │    │  - Real-time Events          │
│  - recipients        │    │  - Locks & Counters          │
│  - email_logs        │    └──────────────────────────────┘
│  - verification_jobs │
└──────────────────────┘
```

## 🔑 Key Design Decisions

### 1. Background Persistence (THE CRITICAL PART)

**Problem:** Windows GUI runs on local machine. Web app needs to run independently of browser.

**Solution:** Celery background workers

```python
# User clicks "Start Campaign" in browser
@app.route('/api/campaigns/<id>/start', methods=['POST'])
def start_campaign(id):
    campaign = Campaign.query.get(id)
    campaign.status = 'running'
    db.session.commit()
    
    # Queue background task (THIS IS THE KEY!)
    task = bulk_send_campaign.delay(campaign.id)
    campaign.celery_task_id = task.id
    db.session.commit()
    
    return {'status': 'started', 'task_id': task.id}

# Background worker processes campaign (RUNS INDEPENDENTLY!)
@celery.task(bind=True)
def bulk_send_campaign(self, campaign_id):
    """This runs in background worker, not web server!"""
    campaign = Campaign.query.get(campaign_id)
    
    while campaign.status == 'running':
        # Get next recipient
        recipient = get_next_unsent_recipient(campaign_id)
        if not recipient:
            break
        
        # Get next SMTP (thread-safe rotation)
        smtp = get_next_smtp_with_lock(campaign_id)
        
        # Get next FROM address (rotation)
        from_addr = get_next_from_address(campaign_id)
        
        # Send email
        try:
            send_single_email(smtp, from_addr, recipient, campaign.template)
            log_success(campaign_id, recipient.id)
            update_stats(campaign_id, sent=1)
            
            # Emit real-time update (if user is watching)
            emit_progress_update(campaign_id)
            
        except SMTPException as e:
            mark_smtp_failed(smtp.id)
            log_failure(campaign_id, recipient.id, str(e))
        
        # Sleep between sends
        time.sleep(campaign.sleep_interval)
        
        # Re-query campaign status (user might have paused/stopped)
        db.session.refresh(campaign)
    
    # Campaign complete
    campaign.status = 'completed'
    campaign.completed_at = datetime.utcnow()
    db.session.commit()
    emit_campaign_complete(campaign_id)
```

**Result:** 
- User starts campaign → Celery task starts
- User closes browser → Task KEEPS RUNNING
- User reopens browser → Sees live progress from database

### 2. Real-time Updates (When User IS Connected)

**Problem:** User wants to see live progress when watching

**Solution:** WebSocket + Redis pub/sub

```python
# In Celery task (background worker)
def emit_progress_update(campaign_id):
    """Publish update to Redis, Flask picks it up and sends via WebSocket"""
    stats = get_campaign_stats(campaign_id)
    redis_client.publish(
        f'campaign:{campaign_id}:updates',
        json.dumps({
            'sent': stats.sent,
            'failed': stats.failed,
            'progress': stats.progress_percent,
            'current_smtp': stats.current_smtp,
            'timestamp': datetime.utcnow().isoformat()
        })
    )

# In Flask (web server)
@socketio.on('subscribe_campaign')
def handle_subscribe(data):
    """User subscribes to campaign updates"""
    campaign_id = data['campaign_id']
    join_room(f'campaign:{campaign_id}')
    
    # Start Redis listener thread
    threading.Thread(
        target=listen_redis_updates,
        args=(campaign_id,),
        daemon=True
    ).start()

def listen_redis_updates(campaign_id):
    """Listen to Redis pub/sub and forward to WebSocket"""
    pubsub = redis_client.pubsub()
    pubsub.subscribe(f'campaign:{campaign_id}:updates')
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            data = json.loads(message['data'])
            socketio.emit(
                'campaign_update',
                data,
                room=f'campaign:{campaign_id}'
            )
```

### 3. Thread-Safe SMTP Rotation (From Original GUI)

**Critical:** Preserve exact locking mechanism from `smtp_manager.py`

```python
# Database model
class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    smtp_index = db.Column(db.Integer, default=0)  # Current SMTP index
    smtp_lock_key = db.Column(db.String(50))  # Redis lock key
    
# In background task
def get_next_smtp_with_lock(campaign_id):
    """Thread-safe SMTP rotation using Redis lock"""
    campaign = Campaign.query.get(campaign_id)
    lock_key = f'campaign:{campaign_id}:smtp_lock'
    
    # Acquire Redis lock (works across multiple Celery workers!)
    with redis_client.lock(lock_key, timeout=10):
        # Get current index
        index = campaign.smtp_index
        smtps = campaign.smtp_servers  # Relationship
        
        # Skip failed servers
        attempts = 0
        while attempts < len(smtps):
            smtp = smtps[index % len(smtps)]
            
            if smtp.failures < 10:  # Not permanently failed
                # Update index for next call
                campaign.smtp_index = (index + 1) % len(smtps)
                db.session.commit()
                return smtp
            
            index += 1
            attempts += 1
        
        # All SMTPs failed
        raise NoAvailableSMTPError()
```

### 4. Email Verification via IMAP (Port from verification_manager.py)

```python
@celery.task
def verify_from_addresses(verification_id):
    """Background task: Send test emails, check IMAP for delivery"""
    verification = Verification.query.get(verification_id)
    
    # Phase 1: Send test emails with tracking IDs
    tracking_ids = {}
    for from_addr in verification.from_addresses:
        tracking_id = f"VER-{uuid.uuid4().hex[:12]}"
        tracking_ids[tracking_id] = from_addr.email
        
        send_test_email(
            smtp=verification.test_smtp,
            from_addr=from_addr.email,
            to=verification.test_recipient,
            subject=f"Verification Test {tracking_id}",
            body=f"<p>Tracking: {tracking_id}</p>"
        )
    
    # Phase 2: Wait
    time.sleep(verification.wait_time)  # Default 5 minutes
    
    # Phase 3: Check IMAP inbox
    imap = connect_imap(
        host=verification.imap_host,
        username=verification.imap_username,
        password=verification.imap_password
    )
    
    delivered_tracking_ids = search_imap_for_tracking_ids(
        imap, 
        list(tracking_ids.keys())
    )
    
    # Phase 4: Update database
    for tracking_id in delivered_tracking_ids:
        from_email = tracking_ids[tracking_id]
        from_addr = FromAddress.query.filter_by(
            email=from_email,
            verification_id=verification_id
        ).first()
        from_addr.status = 'verified'
        from_addr.verified_at = datetime.utcnow()
    
    db.session.commit()
    emit_verification_complete(verification_id)
```

### 5. Inbox Monitoring (Port from inbox_monitor.py)

```python
@celery.task
def monitor_inbox_continuous(monitor_id):
    """Background task: Continuously monitor IMAP for new emails"""
    monitor = InboxMonitor.query.get(monitor_id)
    
    imap = connect_imap(
        host=monitor.imap_host,
        username=monitor.imap_username,
        password=monitor.imap_password
    )
    
    seen_message_ids = set(monitor.seen_message_ids or [])
    
    while monitor.status == 'running':
        # Check for new messages
        message_ids = imap.search(None, 'ALL')[1][0].split()
        
        for msg_id in message_ids:
            if msg_id in seen_message_ids:
                continue
            
            # Fetch message
            msg_data = imap.fetch(msg_id, '(RFC822)')[1][0][1]
            email_msg = email.message_from_bytes(msg_data)
            
            # Extract FROM address
            from_header = email_msg['From']
            from_email = extract_email_from_header(from_header)
            
            # Save to database
            collected = CollectedFromAddress(
                email=from_email,
                monitor_id=monitor_id,
                collected_at=datetime.utcnow()
            )
            db.session.add(collected)
            
            seen_message_ids.add(msg_id)
        
        # Update seen list
        monitor.seen_message_ids = list(seen_message_ids)
        db.session.commit()
        
        # Emit real-time update
        emit_new_from_collected(monitor_id, from_email)
        
        # Sleep before next check
        time.sleep(monitor.check_interval)  # Default 30 seconds
        
        # Re-query status (user might have stopped)
        db.session.refresh(monitor)
```

## 📦 Database Schema

```python
# Campaign and sending
class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    status = db.Column(db.String(20))  # queued, running, paused, stopped, completed
    template = db.Column(db.Text)
    subject = db.Column(db.String(500))
    sleep_interval = db.Column(db.Float, default=1.0)
    thread_count = db.Column(db.Integer, default=10)
    smtp_index = db.Column(db.Integer, default=0)  # Current rotation index
    celery_task_id = db.Column(db.String(50))
    created_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    recipients = db.relationship('Recipient', backref='campaign', lazy='dynamic')
    smtp_servers = db.relationship('SMTPServer', secondary='campaign_smtps')
    from_addresses = db.relationship('FromAddress', secondary='campaign_froms')

class Recipient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))
    email = db.Column(db.String(255))
    status = db.Column(db.String(20))  # pending, sent, failed
    sent_at = db.Column(db.DateTime)
    error = db.Column(db.Text)

class SMTPServer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    host = db.Column(db.String(255))
    port = db.Column(db.Integer)
    username = db.Column(db.String(255))
    password = db.Column(db.String(255))  # Encrypted
    failures = db.Column(db.Integer, default=0)
    successes = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)
    status = db.Column(db.String(20))  # active, disabled, testing

class FromAddress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255))
    display_name = db.Column(db.String(255))
    status = db.Column(db.String(20))  # unverified, verified, dead
    verified_at = db.Column(db.DateTime)
    last_used = db.Column(db.DateTime)

class EmailLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))
    recipient_email = db.Column(db.String(255))
    from_email = db.Column(db.String(255))
    smtp_used = db.Column(db.String(255))
    status = db.Column(db.String(20))  # sent, failed
    error = db.Column(db.Text)
    sent_at = db.Column(db.DateTime)

# Verification
class Verification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mode = db.Column(db.String(20))  # all, verified, unverified
    test_recipient = db.Column(db.String(255))
    test_smtp_id = db.Column(db.Integer)
    imap_host = db.Column(db.String(255))
    imap_username = db.Column(db.String(255))
    imap_password = db.Column(db.String(255))
    wait_time = db.Column(db.Integer, default=300)  # 5 minutes
    status = db.Column(db.String(20))  # running, completed, failed
    celery_task_id = db.Column(db.String(50))
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    from_addresses = db.relationship('FromAddress', secondary='verification_froms')

# Inbox monitoring
class InboxMonitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    imap_host = db.Column(db.String(255))
    imap_username = db.Column(db.String(255))
    imap_password = db.Column(db.String(255))
    check_interval = db.Column(db.Integer, default=30)  # seconds
    status = db.Column(db.String(20))  # running, stopped
    seen_message_ids = db.Column(db.JSON)  # List of seen UIDs
    celery_task_id = db.Column(db.String(50))
    started_at = db.Column(db.DateTime)

class CollectedFromAddress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monitor_id = db.Column(db.Integer, db.ForeignKey('inbox_monitor.id'))
    email = db.Column(db.String(255))
    display_name = db.Column(db.String(255))
    collected_at = db.Column(db.DateTime)
```

## 🚀 Deployment Configuration

```yaml
# render.yaml
services:
  # Web service - Flask API
  - type: web
    name: email-platform-api
    env: python
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --worker-class eventlet -w 1 app:app --bind 0.0.0.0:5000
    plan: standard  # $7/month (must be always-on)
    envVars:
      - key: FLASK_ENV
        value: production
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        fromDatabase:
          name: email-platform-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: email-platform-redis
          type: redis
          property: connectionString
  
  # Worker service - Celery background tasks
  - type: worker
    name: email-platform-worker
    env: python
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A tasks.celery_app worker --loglevel=info --concurrency=10
    plan: standard  # $7/month
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: email-platform-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: email-platform-redis
          type: redis
          property: connectionString

databases:
  - name: email-platform-db
    plan: starter  # $7/month (persistent)
  
  - name: email-platform-redis
    plan: starter  # $10/month
```

## 📱 Frontend React Dashboard

```jsx
// CampaignManager.jsx
function CampaignManager() {
  const [campaign, setCampaign] = useState(null);
  const [stats, setStats] = useState({});
  const socket = useSocket();
  
  useEffect(() => {
    // Subscribe to real-time updates
    socket.emit('subscribe_campaign', { campaign_id: campaign.id });
    
    socket.on('campaign_update', (data) => {
      setStats(data);
    });
    
    return () => {
      socket.emit('unsubscribe_campaign', { campaign_id: campaign.id });
    };
  }, [campaign.id]);
  
  const startCampaign = async () => {
    await axios.post(`/api/campaigns/${campaign.id}/start`);
  };
  
  const pauseCampaign = async () => {
    await axios.post(`/api/campaigns/${campaign.id}/pause`);
  };
  
  const stopCampaign = async () => {
    await axios.post(`/api/campaigns/${campaign.id}/stop`);
  };
  
  return (
    <div>
      <h2>{campaign.name}</h2>
      <div className="stats">
        <div>Sent: {stats.sent} / {stats.total}</div>
        <div>Failed: {stats.failed}</div>
        <div>Progress: {stats.progress}%</div>
        <div>Current SMTP: {stats.current_smtp}</div>
      </div>
      <div className="controls">
        <button onClick={startCampaign}>▶️ Start</button>
        <button onClick={pauseCampaign}>⏸️ Pause</button>
        <button onClick={stopCampaign}>⏹️ Stop</button>
      </div>
      <ProgressBar percent={stats.progress} />
      <LiveChart data={stats.history} />
    </div>
  );
}
```

## ✅ Key Features Ported from Windows GUI

### ✅ Background Persistence
- ✅ Campaigns run in Celery workers (independent of web session)
- ✅ User can close browser, campaign continues
- ✅ Reopen browser, see live progress from database

### ✅ SMTP Rotation
- ✅ Thread-safe rotation using Redis locks
- ✅ Auto-disable after 10 failures
- ✅ Success counter resets failures
- ✅ Auto-cleanup of dead SMTPs

### ✅ FROM Address Verification
- ✅ Send test emails with tracking IDs
- ✅ Check IMAP inbox for delivery
- ✅ Verify vs Unverified lists
- ✅ Auto-remove dead addresses

### ✅ Real-time Updates
- ✅ WebSocket updates when user is watching
- ✅ Live statistics dashboard
- ✅ Progress bar and counters

### ✅ Inbox Monitoring
- ✅ Continuous IMAP monitoring
- ✅ Collect new FROM addresses
- ✅ Background task runs independently

### ✅ Template Personalization
- ✅ Variables: {RECIPIENT}, {NAME}, {DATE}, {RAND:1-100}
- ✅ HTML template editor

## 🎯 User Experience

1. **User starts campaign**
   - Click "Start Campaign" in dashboard
   - Campaign queued to Celery
   - Background worker picks up task
   - Dashboard shows "Running" status

2. **User closes browser**
   - Campaign KEEPS RUNNING in background
   - Database tracks progress
   - Emails continue sending

3. **User reopens browser**
   - Dashboard fetches latest stats from database
   - Shows: "Sent 450 / 1000 (45%)"
   - WebSocket reconnects for live updates
   - Can pause/stop campaign

4. **Campaign completes**
   - Background worker marks campaign complete
   - Final stats saved to database
   - If user is watching: Real-time notification
   - If user is away: Will see "Completed" when they return

## 💰 Cost Estimate

**Production Setup:**
- Web Service (Flask): $7/month
- Worker Service (Celery): $7/month
- PostgreSQL: $7/month
- Redis: $10/month
- **Total: $31/month**

**Free Tier (Limited):**
- Web Service: Free (spins down after 15 min)
- PostgreSQL: Free (90 days, 1GB)
- Worker: NOT POSSIBLE (workers need to be always-on)
- **Not viable for background tasks**

## 🚀 Next Steps

1. Build Celery task system with campaign sending logic
2. Implement Redis-based SMTP rotation locks
3. Port verification system with IMAP checking
4. Create WebSocket real-time update system
5. Build React dashboard with live statistics
6. Deploy to Render with worker service
7. Test: Start campaign → Close browser → Reopen → Verify still running
