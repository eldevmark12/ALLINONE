# SMTP Sent Counter System

## Overview
Comprehensive tracking system that counts **every successful email sent** through each SMTP server across **all parts of the system**. The counter is updated in real-time and persists to `Basic/smtp.txt`.

## Features
✅ **Universal Tracking** - Counts emails from ALL sending systems  
✅ **Thread-Safe** - Uses locks to prevent counter corruption  
✅ **Real-Time Updates** - Counter updates immediately after each send  
✅ **Persistent Storage** - Saves to smtp.txt after every email  
✅ **No System Crashes** - Safe error handling with try-catch blocks  

## Tracked Systems

### 1. **Campaign System** (`/campaign` page)
- **Location**: `campaign_sender.py` line 163
- **Trigger**: After successful `server.sendmail()`
- **Function**: `increment_smtp_sent_count(smtp_server['username'])`
- Counts every email sent during bulk campaign operations

### 2. **Recheck Campaign** (Check Froms feature)
- **Location**: `app.py` line 2131
- **Trigger**: After successful `server.send_message(msg)`
- **Function**: `increment_smtp_sent_count(smtp_server['username'])`
- Counts test emails sent to verify "from" addresses

### 3. **Sending System** (`/sending` page)
- **Location**: `app.py` line 2527
- **Trigger**: After successful `server.send_message(msg)`
- **Function**: `increment_smtp_sent_count(smtp_server['username'])`
- Counts emails sent via the direct sending interface

### 4. **SMTP Validation** (`/smtp` page)
- **Location**: `smtp_validator.py` line 79
- **Trigger**: After successful `server.send_message(msg)`
- **Function**: `increment_smtp_sent_count(account['email'])`
- Counts test emails sent during SMTP validation checks

## Core Function

```python
def increment_smtp_sent_count(smtp_username):
    """
    Increment sent count for a specific SMTP server by 1.
    Thread-safe and works across all sending systems.
    
    Args:
        smtp_username: The username/email of the SMTP server
    """
    with smtp_counter_lock:
        # Read smtp.txt
        # Find matching SMTP by username
        # Increment count by 1
        # Write back to file
        # Log the update
```

## File Format
**smtp.txt** structure:
```
host,port,username,password,status,sent
mail.example.com,587,user@example.com,pass123,active,0
```

**Column 6 (sent)**: Stores the total count of successfully sent emails

## Thread Safety
- **Global Lock**: `smtp_counter_lock = threading.Lock()`
- **Protected Operations**: All file reads/writes are inside `with smtp_counter_lock:`
- **Prevents**: Race conditions when multiple threads send emails simultaneously

## Error Handling
Each counter call is wrapped in try-catch:
```python
try:
    from app import increment_smtp_sent_count
    increment_smtp_sent_count(smtp_server['username'])
except Exception as counter_error:
    # Log warning but don't crash the sending operation
    print(f"⚠️ Failed to update SMTP counter: {str(counter_error)[:50]}")
```

**Critical**: Counter failures do NOT crash email sending operations!

## Usage in SMTP Page
The **Sent** column in `/smtp` page now shows:
- Total emails successfully sent through each SMTP
- Updates in real-time as campaigns run
- Persists across server restarts (stored in smtp.txt)

## Monitoring
Console logs show counter updates:
```
[SMTP COUNTER] ✅ user@example.com: 42 → 43
[SMTP COUNTER] ✅ user@example.com: 43 → 44
```

## Verification
To verify counter is working:
1. Go to `/smtp` page - note current "Sent" count
2. Send test email from `/campaign`, `/sending`, or validate SMTP
3. Refresh `/smtp` page - count should increase by 1 per successful send
4. Check console logs for `[SMTP COUNTER]` messages

## Benefits
✅ **Performance Tracking** - See which SMTPs are most used  
✅ **Quota Management** - Track total emails sent per SMTP  
✅ **Reliability Metrics** - Identify high-performing SMTPs  
✅ **Billing/Limits** - Monitor usage against SMTP provider limits  
✅ **Debugging** - Verify emails are actually being sent  

## Maintenance
- Counter stored in 6th column of smtp.txt
- Manual reset: Edit smtp.txt and change sent value to 0
- Automatic: Counter only increases, never decreases
- No cleanup needed - file size remains small

## Integration Notes
- Works with existing SMTP validation system
- Compatible with active/inactive SMTP filtering
- Does not interfere with campaign sending logic
- Safe to deploy - backwards compatible with old smtp.txt files
