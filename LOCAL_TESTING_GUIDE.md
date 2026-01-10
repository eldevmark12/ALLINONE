# Local Testing Guide - ALL-in-One Email Portal

## Prerequisites

✅ **Python 3.8+** installed  
✅ **pip** (Python package manager)  
✅ **Git** (already installed)  
✅ **SMTP accounts** for testing  
✅ **Text editor** (VS Code, Notepad++, etc.)

---

## Step 1: Install Dependencies

Open PowerShell in the project directory and run:

```powershell
cd "C:\Users\Administrator\Documents\GitHub\ALLINONE"

# Install required Python packages
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed Flask-3.0.0 Flask-SocketIO-5.3.5 python-socketio-5.10.0 ...
```

---

## Step 2: Configure Environment Variables

Create a `.env` file in the project root:

```powershell
# Create .env file
New-Item -Path ".env" -ItemType File -Force

# Add configuration
@"
PASSWORD=@OLDISGOLD2026@
SECRET_KEY=your-secret-key-for-sessions-change-this
PORT=5000
EMAIL_API_KEY=@oldisgold@
"@ | Out-File -FilePath ".env" -Encoding utf8
```

**Or manually create `.env` file with:**
```env
PASSWORD=@OLDISGOLD2026@
SECRET_KEY=your-secret-key-for-sessions-change-this
PORT=5000
EMAIL_API_KEY=@oldisgold@
```

---

## Step 3: Verify Configuration Files

Check that these files exist in `Basic/` folder:

```powershell
# List Basic folder contents
Get-ChildItem Basic/
```

**Required files:**
- ✅ `config.ini` - Campaign settings
- ✅ `smtp.txt` - SMTP server list
- ✅ `from.txt` - Sender email addresses
- ✅ `emailx.txt` - Recipient emails
- ✅ `ma.html` - Email HTML template

**If any are missing, create them:**

```powershell
# Create smtp.txt with header
@"
host,port,username,password,status,sent
smtp.gmail.com,587,your@gmail.com,yourpassword,active,0
"@ | Out-File -FilePath "Basic/smtp.txt" -Encoding utf8

# Create from.txt
@"
sender1@example.com
sender2@example.com
"@ | Out-File -FilePath "Basic/from.txt" -Encoding utf8

# Create emailx.txt (recipients)
@"
recipient1@yahoo.com
recipient2@gmail.com
"@ | Out-File -FilePath "Basic/emailx.txt" -Encoding utf8

# Create config.ini
@"
[Settings]
SENDERNAME=Support Team
subject=Test Message
sleeptime=1
threads=5
LETTERPATH=ma.html
important=0
"@ | Out-File -FilePath "Basic/config.ini" -Encoding utf8
```

---

## Step 4: Start the Application

Run the Flask application:

```powershell
# Start the server
python app.py
```

**Expected output:**
```
 * Serving Flask app 'app'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment.
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://192.168.x.x:5000
Press CTRL+C to quit
```

🎉 **Server is now running!**

---

## Step 5: Access the Application

Open your web browser and go to:

```
http://localhost:5000
```

**Login credentials:**
- Password: `@OLDISGOLD2026@` (or whatever you set in .env)

---

## Step 6: Test the Campaign System

### A. Navigate to Campaign Page

1. Login with password
2. Click **"Campaign Manager"** in sidebar
3. You should see 4 tabs: **Settings**, **From Emails**, **Recipients**, **Console**

### B. Configure Settings Tab

1. Click **"Settings"** tab
2. Set:
   - Sender Name: `Test User`
   - Subject: `Test Email {{RANDOM5}}`
   - Message: Simple HTML like `<h1>Hello {{RANDOM}}</h1>`
   - Sleep Time: `1` second
   - Threads: `5` (start small for testing)
3. Click **"Save Configuration"**

### C. Add From Emails

1. Click **"From Emails"** tab
2. Click **"Bulk Add"** button
3. Paste 2-3 email addresses (one per line)
4. Click **"Save"**
5. Verify count updates

### D. Add Recipients

1. Click **"Recipients"** tab
2. Click **"Bulk Add"** button
3. Paste 2-3 test email addresses (use your own emails!)
4. Click **"Save"**
5. Verify count updates

### E. Configure SMTP Accounts

1. Go to **"SMTP"** page (sidebar)
2. Add your SMTP accounts:
   - Host: `smtp.gmail.com`
   - Port: `587`
   - Username: Your email
   - Password: App password (not regular password!)
   - Status: `active`
3. Click **"Add SMTP"**

**Important for Gmail:**
- Use App Password, not regular password
- Enable 2FA first, then create App Password
- Go to: https://myaccount.google.com/apppasswords

### F. Start Campaign

1. Go back to **"Campaign Manager"**
2. Click **"Console"** tab
3. Click **"Start Campaign"** button
4. Watch the console logs in real-time
5. Monitor statistics cards at top

---

## Step 7: Verify SMTP Disabling Fix

### Test Scenario 1: Bad SMTP Account

```powershell
# Add a fake SMTP that will fail
$smtpContent = Get-Content "Basic/smtp.txt"
$smtpContent += "fake.smtp.com,587,bad@test.com,wrongpassword,active,0"
$smtpContent | Out-File "Basic/smtp.txt" -Encoding utf8
```

**Start campaign and watch:**
1. Fake SMTP should fail repeatedly
2. After 10 failures, console should show: `⚠️ SMTP bad@test.com DISABLED after 10 failures`
3. Check `smtp.txt` - status should change to `disabled`
4. Stop and restart campaign
5. Console should show: `🔄 Loaded previously disabled SMTP: bad@test.com`
6. Fake SMTP should NOT be used again

### Test Scenario 2: Thread Safety

```powershell
# Edit config.ini to use more threads
$config = @"
[Settings]
SENDERNAME=Support Team
subject=Test Message
sleeptime=0.1
threads=20
LETTERPATH=ma.html
important=0
"@
$config | Out-File "Basic/config.ini" -Encoding utf8
```

**Start campaign and observe:**
1. Console should show: `🔧 Using 20 threads for parallel sending`
2. Multiple emails sending simultaneously
3. SMTPs distributed evenly (check console logs)
4. No duplicate SMTP usage at same time

---

## Step 8: Monitor and Debug

### Real-time Monitoring

**Console logs show:**
- ✓ SENT - Successful sends
- ✗ FAILED - Failed attempts
- ⚠️ DISABLED - SMTP disabled after failures
- 🔄 - SMTP queue refilling
- 📊 - Statistics updates

### Check SMTP Status

```powershell
# View current SMTP status
Get-Content "Basic/smtp.txt"
```

Look for:
- `active` - Working SMTPs
- `inactive` - Paused manually
- `disabled` - Auto-disabled after 10 failures

### View Campaign Logs

Watch the terminal where `python app.py` is running for detailed logs.

---

## Common Issues and Fixes

### Issue 1: Port Already in Use

```
OSError: [WinError 10048] Only one usage of each socket address
```

**Fix:**
```powershell
# Change port in .env file
PORT=5001
```

### Issue 2: SMTP Authentication Failed

```
✗ FAILED recipient@email.com | SMTP Auth Failed: smtp_user@gmail.com
```

**Fix:**
- Use App Password for Gmail/Yahoo
- Check username/password in smtp.txt
- Verify SMTP host/port are correct

### Issue 3: No From Emails Found

```
Error: No from emails found
```

**Fix:**
```powershell
# Check from.txt has emails
Get-Content "Basic/from.txt"

# Add emails if empty
@"
test1@example.com
test2@example.com
"@ | Out-File "Basic/from.txt" -Encoding utf8
```

### Issue 4: "No active SMTP servers available"

**Fix:**
```powershell
# Check smtp.txt status column
Get-Content "Basic/smtp.txt"

# Re-enable disabled SMTPs manually
# Edit smtp.txt and change "disabled" to "active"
```

---

## Performance Testing

### Small Test (Recommended First)

```
From Emails: 10
Recipients: 3
Threads: 5
Sleep Time: 1 second
Expected Duration: ~2 minutes
```

### Medium Test

```
From Emails: 100
Recipients: 10
Threads: 10
Sleep Time: 0.5 seconds
Expected Duration: ~5-10 minutes
```

### Large Test (After verification)

```
From Emails: 1000+
Recipients: 10+
Threads: 20-30
Sleep Time: 0.1-0.5 seconds
Expected Duration: Varies
```

---

## Stopping the Application

### Gracefully Stop Campaign

1. Click **"Stop Campaign"** button in Console tab
2. Wait for current sends to complete

### Stop Server

```powershell
# In the terminal where app.py is running
Press CTRL+C
```

---

## Before Deploying to Replit

✅ **Checklist:**

1. ✅ SMTP disabling works (disabled SMTPs not reused after restart)
2. ✅ Threads distribute SMTPs evenly (no race conditions)
3. ✅ Campaign completes successfully
4. ✅ Console logs are clear and helpful
5. ✅ Statistics update in real-time
6. ✅ From emails removed from file after use
7. ✅ `smtp.txt` status column updates correctly

---

## Replit Deployment Notes

When ready to deploy to Replit:

1. **Environment Variables**: Add to Replit Secrets:
   ```
   PASSWORD=@OLDISGOLD2026@
   SECRET_KEY=your-secret-key
   PORT=10000
   ```

2. **File Persistence**: Replit may reset files, so:
   - Critical: `smtp.txt` status persistence
   - Monitor: `from.txt` (should decrease as used)

3. **Port**: Replit uses port `10000` by default (already configured)

4. **Public Access**: Replit provides public URL automatically

---

## Quick Reference Commands

```powershell
# Start server
python app.py

# Install dependencies
pip install -r requirements.txt

# Check Python version
python --version

# View logs
Get-Content "Basic/smtp.txt"

# Reset SMTP statuses (re-enable all)
(Get-Content "Basic/smtp.txt") -replace ',disabled,', ',active,' | Set-Content "Basic/smtp.txt"

# Clear recipients
"" | Out-File "Basic/emailx.txt" -Encoding utf8

# Clear from emails
"" | Out-File "Basic/from.txt" -Encoding utf8
```

---

## Testing Checklist

Before declaring success:

- [ ] Application starts without errors
- [ ] Can login with password
- [ ] Can add from emails
- [ ] Can add recipients
- [ ] Can configure SMTP accounts
- [ ] Campaign starts and sends emails
- [ ] Failed SMTPs get disabled after 10 attempts
- [ ] Disabled SMTPs persist after app restart
- [ ] Console shows real-time logs
- [ ] Statistics update correctly
- [ ] Can stop campaign gracefully
- [ ] Multiple threads work without errors

---

## Support

If you encounter issues:

1. Check terminal logs for error messages
2. Verify all configuration files exist
3. Check SMTP credentials are correct
4. Review [FIXES_DOCUMENTATION.md](FIXES_DOCUMENTATION.md)
5. Test with smaller campaign first (10 emails, 5 threads)

---

**Happy Testing! 🚀**

Once local testing is successful, deployment to Replit will be smooth.
