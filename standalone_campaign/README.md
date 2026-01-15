# Standalone Email Campaign Sender

A standalone Python script for sending bulk emails without any web interface. All configuration is hardcoded except the "from" email addresses which are loaded from a text file.

## Features

- ✅ **Fully Standalone** - No database, no web server, just run the script
- ✅ **Multi-threaded** - 8 concurrent threads for fast sending
- ✅ **SMTP Pooling** - 9 hardcoded SMTP servers with automatic rotation
- ✅ **Auto-recovery** - Automatically disables failed SMTPs after 5 failures
- ✅ **Queue System** - Thread-safe SMTP distribution with automatic refilling
- ✅ **Progress Tracking** - Real-time console output with statistics
- ✅ **Keyboard Interrupt** - Graceful shutdown with Ctrl+C

## Hardcoded Configuration

### SMTP Servers (9 servers)
```
smtp.bajoria.in (anant.kumar@bajoria.in)
mail.al-amoudi.net (ma@al-amoudi.net)
smtp.centrum.sk (mjmj@centrum.sk)
mail.msd-consulting.co.za (tjacobs@msd-consulting.co.za)
mail.atharvrajtranslinks.net (pravinbh@atharvrajtranslinks.net)
mail.atharvrajtranslinks.net (info@atharvrajtranslinks.net)
mail.isianpadu.com (danish.ismail@isianpadu.com)
mail.poligon.in (portoffice@phonexgroup.com)
mail.buyspectra.com (design3@buyspectra.com)
```

### Recipients (10 test addresses)
```
Footmen404@yahoo.com
laststand2026@yahoo.com
azoofozora2026@yahoo.com
bravoeco2026@yahoo.com
Footmen203@yahoo.com
micoland2026@yahoo.com
atombrid2069@yahoo.com
azoofoo2026@yahoo.com
brb4mints@yahoo.com
copermerv2026@yahoo.com
```

### Campaign Settings
- **Threads**: 8 concurrent workers
- **Sleep Time**: 1 second between emails (per thread)
- **Sender Name**: "Support"
- **Subject**: "hello {random5}" (random 5-char string)
- **HTML Template**: Professional greeting message

## Installation

1. Navigate to the standalone_campaign folder:
```bash
cd standalone_campaign
```

2. No dependencies needed - uses only Python standard library!

## Usage

### Step 1: Prepare Your From Emails

Edit `from.txt` and add one email address per line:

```
john@company1.com
jane@company2.com
support@business.com
```

### Step 2: Run the Campaign

```bash
python campaign.py
```

Or on Windows:
```bash
py campaign.py
```

### Step 3: Confirm Start

The script will display the configuration and ask for confirmation:

```
📊 Configuration:
   • SMTPs: 9 servers
   • Recipients: 10 addresses
   • From File: from.txt
   • Threads: 8
   • Sleep Time: 1s

🚀 Start campaign? (yes/no):
```

Type `yes` and press Enter to start.

## Output Example

```
[19:45:23] ℹ️ 📧 Loaded 100 from emails from from.txt
[19:45:23] ℹ️ 📊 Configuration:
[19:45:23] ℹ️    • SMTP Servers: 9
[19:45:23] ℹ️    • Recipients: 10
[19:45:23] ℹ️    • From Emails: 100
[19:45:23] ℹ️    • Threads: 8
[19:45:23] ℹ️    • Total Emails: 1,000
[19:45:25] ✅ Progress: 10/1,000 (1.0%) | Failed: 0 | Active SMTPs: 9
[19:45:28] ✅ Progress: 20/1,000 (2.0%) | Failed: 0 | Active SMTPs: 9
...
[19:48:15] 📊 CAMPAIGN COMPLETED
[19:48:15] ✅ Total Sent: 998
[19:48:15] ❌ Total Failed: 2
[19:48:15] 📧 Unique From Emails Used: 100
[19:48:15] ⚠️ Disabled SMTPs: 1
[19:48:15] ⏱️ Duration: 172s (2.9 minutes)
[19:48:15] 🚀 Rate: 5.8 emails/second
```

## How It Works

1. **Load From Emails**: Reads all email addresses from `from.txt`
2. **Create Tasks**: Generates all combinations of (from_email × recipient)
3. **SMTP Queue**: Pre-loads queue with 100 copies of each SMTP server (900 total)
4. **Multi-threading**: 8 worker threads process tasks concurrently
5. **SMTP Fetch**: Each worker fetches SMTP from queue when ready to send
6. **Auto-refill**: When queue empties, refills with active SMTPs × 100
7. **Failure Tracking**: Disables SMTPs after 5 consecutive failures
8. **SMTP Recycling**: Returns successful SMTPs to queue for reuse

## Stopping the Campaign

Press `Ctrl+C` to gracefully stop the campaign at any time.

## Customization

To modify the hardcoded configuration, edit `campaign.py`:

### Change Recipients
```python
RECIPIENTS = [
    'your@email.com',
    'another@email.com'
]
```

### Change SMTP Servers
```python
SMTP_SERVERS = [
    {
        'host': 'smtp.example.com',
        'port': 587,
        'username': 'user@example.com',
        'password': 'yourpassword'
    }
]
```

### Change HTML Template
```python
HTML_TEMPLATE = """<html>
<body>
    Your custom HTML here
    Use {from_email} to insert sender
</body>
</html>"""
```

### Change Settings
```python
SENDER_NAME = "Your Name"
SUBJECT_TEMPLATE = "Your Subject {random5}"
THREAD_COUNT = 8
SLEEP_TIME = 1
```

## Technical Details

- **Language**: Python 3.7+
- **Dependencies**: None (uses standard library only)
- **Thread Safety**: Queue-based SMTP distribution
- **Error Handling**: Automatic retry and SMTP disabling
- **Performance**: ~6-10 emails/second (depends on SMTP response time)

## Troubleshooting

### "from.txt not found"
Create a `from.txt` file in the same directory with one email per line.

### "All SMTPs disabled"
All 9 SMTP servers have failed. Check:
- SMTP credentials are correct
- SMTP servers are online
- Firewall allows SMTP connections (port 587)

### Low sending rate
- Increase `THREAD_COUNT` (default: 8)
- Decrease `SLEEP_TIME` (default: 1 second)
- Check SMTP server response times

## License

For internal use only. Contains hardcoded SMTP credentials.

## Version

**Version 1.0** - January 2026  
Created from production configuration at http://163.5.254.109:10000/campaign
