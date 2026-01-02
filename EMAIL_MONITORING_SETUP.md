# Email Monitoring API - Setup Guide

## Overview
This document explains how to configure your external email monitoring script to send data to your ALL-in-One portal.

---

## 🔐 Step 1: API Key Configuration

### Default API Key:
The API key is already configured as: **`@oldisgold@`**

You can use this immediately in your monitoring script without any Render configuration.

### Optional - Custom API Key:
If you want to use a custom API key for additional security:
1. Go to your Render dashboard: https://dashboard.render.com
2. Select your `ALL-in-One` service
3. Go to **Environment** tab
4. Add a new environment variable:
   - **Key:** `EMAIL_API_KEY`
   - **Value:** Your custom secure key
5. Click **Save Changes** (app will redeploy)
6. Update your monitoring script to use the new key

---

## 📡 Step 2: Configure Your Monitoring Script

### Base Configuration:
```python
# Configuration for your monitoring script
API_URL = "https://all-in-one-tdxd.onrender.com/api"
API_KEY = "@oldisgold@"  # Default API key

# Headers for all API requests
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
```

---

## 🚀 API Endpoints to Implement

### 1. POST /api/initial_scan
**When to call:** On script startup, after collecting all emails from all accounts

**Python Example:**
```python
import requests
import json

def send_initial_scan(all_accounts_data):
    """
    Send initial scan with all accounts and emails
    
    Args:
        all_accounts_data: Dictionary with account info
    """
    
    # Calculate totals
    total_accounts = len(all_accounts_data)
    total_emails = sum(len(account['emails']) for account in all_accounts_data)
    
    # Prepare payload
    payload = {
        "total_accounts": total_accounts,
        "total_emails": total_emails,
        "accounts": []
    }
    
    # Process each account
    for account_name, account_info in all_accounts_data.items():
        # Extract unique from emails
        from_emails = list(set([email['from_email'] for email in account_info['emails']]))
        
        account_data = {
            "account_name": account_name,
            "from_emails": from_emails,
            "emails": [
                {
                    "from_email": email['from_email'],
                    "subject": email['subject'],
                    "date": email['date']
                }
                for email in account_info['emails']
            ]
        }
        payload['accounts'].append(account_data)
    
    # Send to API
    try:
        response = requests.post(
            f"{API_URL}/initial_scan",
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"✅ Initial scan sent: {total_accounts} accounts, {total_emails} emails")
            return True
        else:
            print(f"❌ Initial scan failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending initial scan: {e}")
        return False
```

**Real Example Data Structure:**
```python
# Example of all_accounts_data structure:
all_accounts_data = {
    "imap.mail.yahoo-1.com": {
        "emails": [
            {
                "from_email": "sender1@example.com",
                "from_raw": "Sender Name <sender1@example.com>",
                "to": "your-account@yahoo.com",
                "subject": "Welcome Email",
                "date": "Thu, 02 Jan 2026 10:30:00 +0100",
                "timestamp": "2026-01-02 10:30:00"
            },
            # ... more emails
        ]
    },
    "imap.mail.yahoo-2.com": {
        # ... similar structure
    }
}
```

---

### 2. POST /api/new_email
**When to call:** Immediately when a new email is detected (real-time)

**Python Example:**
```python
def send_new_email(account_name, email_data):
    """
    Send notification about a single new email
    
    Args:
        account_name: IMAP account identifier (e.g., "imap.mail.yahoo-1.com")
        email_data: Dictionary with email details
    """
    
    payload = {
        "account_name": account_name,
        "from_email": email_data['from_email'],
        "from_raw": email_data['from_raw'],
        "to": email_data['to'],
        "subject": email_data['subject'],
        "date": email_data['date'],
        "timestamp": email_data['timestamp']
    }
    
    try:
        response = requests.post(
            f"{API_URL}/new_email",
            headers=HEADERS,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"📧 New email sent: {account_name} - {email_data['from_email']}")
            return True
        else:
            print(f"❌ Failed to send new email: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending new email: {e}")
        return False
```

**Real Example Call:**
```python
# When you detect a new email in your monitoring loop:
new_email_data = {
    "from_email": "johndoe@example.com",
    "from_raw": "John Doe <johndoe@example.com>",
    "to": "your-account@yahoo.com",
    "subject": "Meeting Tomorrow",
    "date": "Thu, 02 Jan 2026 14:25:30 +0100",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

send_new_email("imap.mail.yahoo-1.com", new_email_data)
```

---

### 3. POST /api/heartbeat (Optional)
**When to call:** Every 10 check cycles (for monitoring health)

**Python Example:**
```python
def send_heartbeat(check_count, new_emails_count, accounts_count):
    """
    Optional: Send periodic heartbeat
    """
    payload = {
        "check_count": check_count,
        "new_emails_detected": new_emails_count,
        "accounts_monitored": accounts_count
    }
    
    try:
        response = requests.post(
            f"{API_URL}/heartbeat",
            headers=HEADERS,
            json=payload,
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"💓 Heartbeat sent: {check_count} checks")
        
    except Exception as e:
        print(f"⚠️ Heartbeat failed: {e}")
```

---

### 4. POST /api/monitoring_summary (Optional)
**When to call:** When stopping the monitoring script

**Python Example:**
```python
def send_monitoring_summary(total_checks, new_emails, total_emails):
    """
    Optional: Send final summary when stopping
    """
    payload = {
        "total_checks": total_checks,
        "new_emails_detected": new_emails,
        "total_emails_tracked": total_emails
    }
    
    try:
        response = requests.post(
            f"{API_URL}/monitoring_summary",
            headers=HEADERS,
            json=payload,
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"📊 Summary sent successfully")
        
    except Exception as e:
        print(f"⚠️ Summary failed: {e}")
```

---

## 🔄 Complete Integration Example

```python
import requests
import time
from datetime import datetime

# Configuration
API_URL = "https://all-in-one-tdxd.onrender.com/api"
API_KEY = "@oldisgold@"  # Default API key
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

class EmailMonitoringIntegration:
    def __init__(self):
        self.check_count = 0
        self.new_emails_detected = 0
    
    def start_monitoring(self, all_accounts_data):
        """Called once at startup"""
        print("🚀 Starting email monitoring...")
        
        # Send initial scan
        if self.send_initial_scan(all_accounts_data):
            print("✅ Initial scan successful")
        else:
            print("❌ Initial scan failed")
    
    def on_new_email_detected(self, account_name, email_data):
        """Called every time a new email is detected"""
        self.new_emails_detected += 1
        self.send_new_email(account_name, email_data)
    
    def on_check_complete(self):
        """Called after each check cycle"""
        self.check_count += 1
        
        # Send heartbeat every 10 checks
        if self.check_count % 10 == 0:
            self.send_heartbeat()
    
    def on_shutdown(self, total_emails):
        """Called when stopping the script"""
        self.send_monitoring_summary(total_emails)
    
    # ... (include all the send_* methods from above)

# Usage in your monitoring script:
monitor = EmailMonitoringIntegration()

# 1. On startup - send all existing data
all_accounts = collect_all_accounts_and_emails()  # Your function
monitor.start_monitoring(all_accounts)

# 2. In monitoring loop - send new emails in real-time
while monitoring:
    for account in accounts:
        new_emails = check_for_new_emails(account)  # Your function
        for email in new_emails:
            monitor.on_new_email_detected(account.name, email)
    
    monitor.on_check_complete()
    time.sleep(10)  # Check every 10 seconds

# 3. On exit - send summary
monitor.on_shutdown(total_email_count)
```

---

## 🧪 Testing Your Integration

### Test 1: Verify API Key
```python
import requests

response = requests.get(
    "https://all-in-one-tdxd.onrender.com/api/monitored/froms",
    headers={"Authorization": f"Bearer {API_KEY}"}
)

if response.status_code == 401:
    print("❌ API Key is incorrect")
else:
    print("✅ API Key is valid")
```

### Test 2: Send Test Initial Scan
```python
test_data = {
    "total_accounts": 1,
    "total_emails": 2,
    "accounts": [
        {
            "account_name": "test-account",
            "from_emails": ["test@example.com"],
            "emails": [
                {
                    "from_email": "test@example.com",
                    "subject": "Test Email",
                    "date": "Thu, 02 Jan 2026 10:00:00 +0100"
                }
            ]
        }
    ]
}

response = requests.post(
    f"{API_URL}/initial_scan",
    headers=HEADERS,
    json=test_data
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

### Test 3: Send Test New Email
```python
test_email = {
    "account_name": "test-account",
    "from_email": "test@example.com",
    "from_raw": "Test Sender <test@example.com>",
    "to": "your@yahoo.com",
    "subject": "Test Subject",
    "date": "Thu, 02 Jan 2026 10:30:00 +0100",
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

response = requests.post(
    f"{API_URL}/new_email",
    headers=HEADERS,
    json=test_email
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

---

## 📊 Viewing Data in Portal

After sending data:
1. Login to: https://all-in-one-tdxd.onrender.com
2. Go to: **Check Froms** tab
3. Click on: **Sending** tab
4. You'll see:
   - Total accounts monitored
   - Total emails tracked
   - Unique from emails
   - Last update timestamp
   - Table with all accounts and their from email counts

---

## 🔒 Security Notes

1. **Default API key is `@oldisgold@`** - Works out of the box
2. **Use HTTPS only** - Already configured (Render uses HTTPS)
3. **Optional: Set custom key** - Update `EMAIL_API_KEY` env var in Render for custom security
4. **Monitor failed requests** - Check logs for 401 errors

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Verify using API_KEY = "@oldisgold@" exactly |
| 500 Internal Error | Check request payload structure matches examples |
| Timeout errors | Increase timeout in requests (use `timeout=30`) |
| Data not showing | Verify you're logged into portal and on Sending tab |

---

## 📞 Support

If you encounter issues:
1. Check Render logs: https://dashboard.render.com → Your Service → Logs
2. Verify using the correct API key: `@oldisgold@`
3. Test with curl:
```bash
curl -X POST https://all-in-one-tdxd.onrender.com/api/initial_scan \
  -H "Authorization: Bearer @oldisgold@" \
  -H "Content-Type: application/json" \
  -d '{"total_accounts":1,"total_emails":1,"accounts":[]}'
```

---

**Last Updated:** January 2, 2026
**Portal URL:** https://all-in-one-tdxd.onrender.com
**Repository:** https://github.com/adamtheplanetarium/ALL-in-One
