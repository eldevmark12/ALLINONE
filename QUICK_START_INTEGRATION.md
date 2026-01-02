# Quick Start - Add This to Your Monitoring Script

## 🔧 Configuration (Add at top of your script)

```python
import requests
from datetime import datetime

# API Configuration
API_URL = "https://all-in-one-tdxd.onrender.com/api"
API_KEY = "@oldisgold@"  # Fixed API key

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
```

---

## 📤 Function 1: Send Initial Scan (Call ONCE at startup)

```python
def send_initial_scan_to_portal(accounts_data):
    """
    Send all accounts and emails to portal on startup
    
    Args:
        accounts_data: Dict like {"account_name": {"emails": [list of email dicts]}}
    """
    # Build payload
    accounts_list = []
    total_emails = 0
    
    for account_name, account_info in accounts_data.items():
        emails = account_info.get('emails', [])
        total_emails += len(emails)
        
        # Extract unique from emails
        from_emails = list(set([email.get('from_email', '') for email in emails if email.get('from_email')]))
        
        accounts_list.append({
            "account_name": account_name,
            "from_emails": from_emails,
            "emails": [
                {
                    "from_email": email.get('from_email', ''),
                    "subject": email.get('subject', ''),
                    "date": email.get('date', '')
                }
                for email in emails
            ]
        })
    
    payload = {
        "total_accounts": len(accounts_data),
        "total_emails": total_emails,
        "accounts": accounts_list
    }
    
    # Send to API
    try:
        response = requests.post(
            f"{API_URL}/initial_scan",
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"✅ Initial scan sent: {len(accounts_data)} accounts, {total_emails} emails")
        else:
            print(f"❌ Initial scan failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error sending initial scan: {e}")
```

---

## 📧 Function 2: Send New Email (Call for EACH new email detected)

```python
def send_new_email_to_portal(account_name, email_data):
    """
    Send single new email notification to portal
    
    Args:
        account_name: str - IMAP account identifier (e.g., "imap.mail.yahoo-1.com")
        email_data: dict with keys: from_email, from_raw, to, subject, date
    """
    payload = {
        "account_name": account_name,
        "from_email": email_data.get('from_email', ''),
        "from_raw": email_data.get('from_raw', ''),
        "to": email_data.get('to', ''),
        "subject": email_data.get('subject', ''),
        "date": email_data.get('date', ''),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        response = requests.post(
            f"{API_URL}/new_email",
            headers=HEADERS,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"📧 New email sent to portal: {email_data.get('from_email', 'unknown')}")
        else:
            print(f"❌ Failed to send new email: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error sending new email: {e}")
```

---

## 🚀 How to Integrate (3 Simple Steps)

### Step 1: Add configuration at the top of your script
```python
# Add these imports if not already present
import requests
from datetime import datetime

# Add API configuration
API_URL = "https://all-in-one-tdxd.onrender.com/api"
API_KEY = "@oldisgold@"  # Fixed API key
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
```

### Step 2: Copy the two functions above into your script
Just paste `send_initial_scan_to_portal()` and `send_new_email_to_portal()` functions

### Step 3: Call the functions in your code

**A) After collecting all emails on startup:**
```python
# Your existing code that collects all emails
all_accounts = {}  # Your data structure
# ... collect emails into all_accounts ...

# ADD THIS LINE - Send to portal
send_initial_scan_to_portal(all_accounts)
```

**B) When you detect a new email in monitoring loop:**
```python
# Your existing code in monitoring loop
for account in accounts:
    new_emails = check_new_emails(account)  # Your function
    for email in new_emails:
        # ADD THIS LINE - Send each new email to portal
        send_new_email_to_portal(account.name, {
            'from_email': email.from_email,
            'from_raw': email.from_raw,
            'to': email.to,
            'subject': email.subject,
            'date': email.date
        })
```

---

## 🔐 Render Setup (Optional - Already Configured)

The API key is already set to `@oldisgold@` in the code. 

If you want to change it for security:
1. Go to: https://dashboard.render.com
2. Select your **ALL-in-One** service
3. Click **Environment** tab
4. Add new variable:
   - Key: `EMAIL_API_KEY`
   - Value: `your-new-secure-key`
5. Save (app will redeploy)
6. Update `API_KEY` in your monitoring script to match

---

## ✅ Test It

### Quick Test with Fake Data:
```python
# Test 1: Send test initial scan
test_data = {
    "test-account-1": {
        "emails": [
            {
                "from_email": "test@example.com",
                "subject": "Test Email",
                "date": "Thu, 02 Jan 2026 10:00:00 +0100"
            }
        ]
    }
}

send_initial_scan_to_portal(test_data)

# Test 2: Send test new email
test_email = {
    "from_email": "new@example.com",
    "from_raw": "New Sender <new@example.com>",
    "to": "recipient@yahoo.com",
    "subject": "Test Subject",
    "date": "Thu, 02 Jan 2026 11:00:00 +0100"
}

send_new_email_to_portal("test-account-1", test_email)
```

Then check portal at: https://all-in-one-tdxd.onrender.com
- Login
- Go to **Check Froms** → **Sending** tab
- You should see your test data!

---

## 📊 What You'll See in Portal

After sending data, the **Sending** tab will show:
- 📊 **Accounts**: Number of email accounts monitored
- 📧 **Total Emails**: Total emails tracked
- 👤 **Unique Froms**: Number of unique sender emails
- 🕐 **Last Update**: Timestamp of last data received
- 📋 **Table**: List of accounts with from email counts

---

## 🐛 Common Issues

**401 Unauthorized Error:**
- Make sure you're using `API_KEY = "@oldisgold@"` exactly as shown
- Check for any extra spaces or typos
- Solution: Copy the API_KEY from the examples above

**Data not showing in portal:**
- Make sure you're logged in
- Navigate to Check Froms → Sending tab
- Click Refresh button

**Timeout errors:**
- Increase timeout: `timeout=60`
- Check your internet connection

---

## 💡 Full Example Integration

```python
import requests
from datetime import datetime
import time

# Configuration
API_URL = "https://all-in-one-tdxd.onrender.com/api"
API_KEY = "@oldisgold@"  # Fixed API key
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# [Copy the two send functions here from above]

# Your main monitoring script
def main():
    print("Starting email monitoring...")
    
    # 1. Collect all existing emails (your existing code)
    all_accounts = collect_all_accounts()  # Your function
    
    # 2. Send initial scan to portal
    send_initial_scan_to_portal(all_accounts)
    
    # 3. Start monitoring loop (your existing code)
    print("Monitoring for new emails...")
    while True:
        for account_name in all_accounts.keys():
            new_emails = check_for_new_emails(account_name)  # Your function
            
            for email in new_emails:
                # Send each new email to portal
                send_new_email_to_portal(account_name, {
                    'from_email': email.from_email,
                    'from_raw': email.from_raw,
                    'to': email.to,
                    'subject': email.subject,
                    'date': email.date
                })
        
        time.sleep(10)  # Check every 10 seconds

if __name__ == "__main__":
    main()
```

---

**That's it!** 🎉

Just add the configuration, copy the two functions, and call them at the right places.

For full detailed documentation, see: `EMAIL_MONITORING_SETUP.md`
