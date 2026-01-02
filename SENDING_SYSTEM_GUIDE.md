# Sending Campaign System Guide

## Overview
The Sending Campaign System allows you to send emails using monitored "from" email addresses collected via the Email Monitoring API. It features a complete tabbed interface with active/inactive from management, recipients management, campaign settings, and real-time console logging.

## Features

### 1. **Tabbed Interface**
- **Settings Tab**: Configure campaign parameters
- **Active Froms Tab**: View and manage active from emails
- **Inactive Froms Tab**: View and manage inactive from emails
- **Recipients Tab**: Manage recipient list
- **Console Tab**: Real-time campaign logs and controls

### 2. **Active/Inactive From Management**
- All monitored from emails default to "active" status
- Toggle between active/inactive states with one click
- Status persists across server restarts (stored in `Basic/sending_from_status.json`)
- Filter campaign to use only active, only inactive, or all from emails

### 3. **Round-Robin Sending Logic**
- Distributes emails evenly across selected from addresses
- Example: 20 from emails → 100 recipients = each from sends 5 emails
- Configurable to use active, inactive, or all from emails

### 4. **Real-Time Notifications**
- Browser notifications when new monitored emails arrive
- Socket.IO real-time updates in console
- Status badge shows campaign state (Running/Stopped)

### 5. **Campaign Statistics**
- Active from emails count
- Inactive from emails count
- Recipients count
- Emails sent count (updates in real-time)

## How to Use

### Step 1: Receive Monitored From Emails
Monitored from emails are automatically collected via the Email Monitoring API. When external monitoring script calls `/api/initial_scan` or `/api/new_email`, from addresses are stored and become available in the Sending system.

All new from emails are automatically set to "active" status.

### Step 2: Manage Active/Inactive Status
1. Go to **Sending** page in navigation
2. Click **Active Froms** tab to see active from emails
3. Click **Inactive Froms** tab to see inactive from emails
4. Click **Activate** or **Deactivate** buttons to toggle status
5. Status changes are saved immediately and persist across restarts

### Step 3: Add Recipients
1. Click **Recipients** tab
2. Click **Bulk Add** button
3. Paste email addresses (one per line)
4. Click **Add Recipients**
5. Duplicates are automatically removed

### Step 4: Configure Settings
1. Click **Settings** tab
2. Configure:
   - **From Email Source**: 
     - "Active Froms Only" - Use only active from emails
     - "Inactive Froms Only" - Use only inactive from emails
     - "All Froms" - Use both active and inactive
   - **Sender Name**: Display name for emails
   - **Subject**: Email subject line
   - **Message**: Email body content
   - **Sleep Time**: Delay between emails (seconds)
   - **Threads**: Number of concurrent sending threads
3. Click **Save Settings**

### Step 5: Start Campaign
1. Click **Console** tab
2. Click **Start Campaign** button
3. Watch real-time logs in console
4. Monitor sent count in statistics cards
5. Click **Stop Campaign** to abort early

## Campaign Logic

### Round-Robin Algorithm
```
For each recipient:
  1. Get next from email (rotating index)
  2. Send email from that address
  3. Increment sent counter
  4. Move to next from email
  5. Sleep for configured delay
```

### From Email Filtering
- **Active Only**: `get_from_status(email) == 'active'`
- **Inactive Only**: `get_from_status(email) == 'inactive'`
- **All**: No filtering applied

### Example Scenario
- **Setup**: 15 active froms, 10 inactive froms, 100 recipients
- **Source = "Active Froms Only"**: Uses 15 active froms
  - Round-robin: Each from sends ~7 emails (100 ÷ 15)
- **Source = "All Froms"**: Uses all 25 froms
  - Round-robin: Each from sends 4 emails (100 ÷ 25)

## Files Structure

### Frontend
- **templates/sending.html**: Complete UI with tabs, modals, and JavaScript

### Backend
- **app.py**: All Sending API endpoints and campaign logic
- **Basic/sending_recipients.txt**: Recipients list (one per line)
- **Basic/sending_config.ini**: Campaign settings (ConfigParser format)
- **Basic/sending_from_status.json**: Active/inactive status persistence

### API Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/monitored/froms` | GET | Get all monitored from emails with status |
| `/api/sending/toggle_from` | POST | Toggle from email active/inactive |
| `/api/sending/save_settings` | POST | Save campaign settings |
| `/api/sending/add_recipients` | POST | Add recipients (bulk) |
| `/api/sending/clear_recipients` | POST | Clear all recipients |
| `/api/sending/recipients` | GET | Get recipient count |
| `/api/sending/start` | POST | Start sending campaign |
| `/api/sending/stop` | POST | Stop sending campaign |
| `/api/sending/status` | GET | Check if campaign running |

## Socket.IO Events

### Client → Server
*None (all actions via HTTP POST)*

### Server → Client
- **new_monitored_email**: New from email received via API
  ```json
  {
    "account": "user@example.com",
    "from": "sender@domain.com",
    "subject": "Email subject",
    "timestamp": "2024-01-15T10:30:00"
  }
  ```

- **sending_campaign_log**: Campaign log message
  ```json
  {
    "message": "Sent to recipient@example.com from sender@domain.com",
    "type": "success"  // success, error, warning, info
  }
  ```

- **sending_campaign_stats**: Campaign statistics update
  ```json
  {
    "sent": 45
  }
  ```

- **sending_campaign_complete**: Campaign finished
  ```json
  {
    "message": "Campaign completed! Sent 100 emails"
  }
  ```

## Helper Functions

### Python (app.py)
```python
load_from_status()              # Load status dict from JSON file
save_from_status(status_dict)   # Save status dict to JSON file
get_from_status(email)          # Get status for email (default: 'active')
set_from_status(email, status)  # Set status for email and save
```

### JavaScript (sending.html)
```javascript
loadMonitoredFroms()            // Fetch and display monitored from emails
toggleFromStatus(email, status) // Toggle active/inactive status
saveSendingSettings()           // Save campaign settings
addBulkRecipients()             // Add recipients from textarea
clearSendingRecipients()        // Clear all recipients
startSendingCampaign()          // Start campaign
stopSendingCampaign()           // Stop campaign
checkSendingStatus()            // Check if campaign running
addToSendingConsole(msg, type)  // Add log to console
```

## Differences from Check Froms Campaign

| Feature | Check Froms | Sending |
|---------|-------------|---------|
| **From Source** | Basic/from.txt file | Monitored API emails |
| **From Management** | File-based removal | Active/inactive toggle |
| **Settings Location** | Basic/config.ini | Basic/sending_config.ini |
| **Recipients** | Basic/emailx.txt | Basic/sending_recipients.txt |
| **Status Persistence** | None (file deletion) | JSON file with status |
| **API Integration** | No | Yes (Email Monitoring API) |
| **Real-time Notifications** | No | Yes (browser notifications) |
| **From Count Updates** | Yes (immediate removal) | No (toggle-based) |

## Troubleshooting

### No From Emails Available
- **Cause**: No monitored emails received via API
- **Solution**: Run external monitoring script to call `/api/initial_scan`

### Campaign Won't Start
- **Possible Causes**:
  1. No recipients added
  2. No from emails match selected source (e.g., "Active Only" but all are inactive)
  3. Campaign already running
- **Solution**: Check Recipients tab count, verify from email status, check Console for error messages

### Status Not Persisting
- **Cause**: File write permissions or JSON file corruption
- **Solution**: Check `Basic/sending_from_status.json` exists and is writable

### Recipients Not Adding
- **Cause**: Empty input or file write error
- **Solution**: Verify textarea has emails (one per line), check file permissions on `Basic/sending_recipients.txt`

## Next Steps

### To Implement SMTP Sending
Currently, the campaign only simulates sending (logs messages). To implement actual SMTP:

1. **Option A**: Store SMTP credentials with monitored accounts
   - Modify Email Monitoring API to accept SMTP server info
   - Store in `monitored_data` alongside from emails
   - Use credentials in `run_sending_campaign()`

2. **Option B**: Use separate SMTP pool
   - Create `Basic/sending_smtp.txt` (similar to Check Froms)
   - Load SMTP accounts in `run_sending_campaign()`
   - Match from emails to SMTP accounts (by domain or mapping)

3. **Update code in `run_sending_campaign()`**:
   ```python
   # Replace this TODO section:
   # TODO: Actually send email here using SMTP
   
   # With actual SMTP sending:
   import smtplib
   from email.mime.text import MIMEText
   
   smtp_account = get_smtp_for_from(current_from)
   msg = MIMEText(message)
   msg['Subject'] = subject
   msg['From'] = f'{sender_name} <{current_from}>'
   msg['To'] = recipient
   
   with smtplib.SMTP(smtp_account['host'], smtp_account['port']) as server:
       server.starttls()
       server.login(smtp_account['user'], smtp_account['pass'])
       server.send_message(msg)
   ```

## Summary

The Sending Campaign System provides:
- ✅ Complete tabbed interface with 5 tabs
- ✅ Active/inactive from email management with persistence
- ✅ Round-robin sending algorithm with filtering
- ✅ Bulk recipient management
- ✅ Real-time console logs via Socket.IO
- ✅ Browser notifications for new monitored emails
- ✅ Campaign status badge (Running/Stopped)
- ✅ Settings persistence via ConfigParser
- ✅ Separate from Check Froms campaign (independent system)

The only remaining task is to implement actual SMTP sending logic (currently simulated).
