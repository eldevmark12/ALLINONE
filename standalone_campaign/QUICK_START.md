# Quick Start Guide - Standalone Campaign

## Setup (30 seconds)

1. **Navigate to folder**:
   ```bash
   cd standalone_campaign
   ```

2. **Add your from emails** to `from.txt`:
   ```
   john@company.com
   jane@business.net
   support@mysite.org
   ```

3. **Run**:
   ```bash
   python campaign.py
   ```
   
4. **Type `yes` when prompted**

That's it! Campaign will run independently.

## What's Hardcoded

✅ **9 SMTP Servers** - All active production servers  
✅ **10 Test Recipients** - Yahoo test addresses  
✅ **HTML Template** - Professional greeting message  
✅ **Settings** - 8 threads, 1s sleep time  

## Only Variable: From Emails

Edit `from.txt` with your sender addresses (one per line).

## Test Run

Default `from.txt` has 3 example addresses.  
This will send: **3 from × 10 recipients = 30 emails**

```bash
python campaign.py
```

## Production Run

Replace `from.txt` with your 1000+ addresses:
```bash
# Copy your from emails
notepad from.txt

# Run campaign
python campaign.py
```

**1,000 from emails × 10 recipients = 10,000 emails sent**

## Stop Anytime

Press `Ctrl+C` to stop gracefully.

## Monitor Progress

Console shows real-time stats every 10 emails:
```
✅ Progress: 50/1,000 (5.0%) | Failed: 0 | Active SMTPs: 9
✅ Progress: 60/1,000 (6.0%) | Failed: 0 | Active SMTPs: 9
```

## Final Summary

At end, shows complete statistics:
```
✅ Total Sent: 998
❌ Total Failed: 2
📧 Unique From Emails Used: 100
⚠️ Disabled SMTPs: 1
⏱️ Duration: 172s (2.9 minutes)
🚀 Rate: 5.8 emails/second
```

## No Dependencies

Uses only Python standard library - no installation needed!

## Safe to Close Terminal

Script runs to completion even if you close the terminal window (on most systems).
