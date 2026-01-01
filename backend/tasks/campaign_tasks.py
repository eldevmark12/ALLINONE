"""
Campaign Background Tasks
Handles bulk email sending with SMTP rotation and persistence
Ported from Fake-client/GUI-Mailer/sending_manager.py
"""
import time
import smtplib
import random
import re
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import email.utils
from datetime import datetime
from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy import and_

from tasks.celery_app import celery
from backend.models import db, Campaign, Recipient, SMTPServer, FromAddress, EmailLog
from backend.utils.encryption import decrypt_password

logger = get_task_logger(__name__)


class CampaignTask(Task):
    """Base task with database session management"""
    
    def after_return(self, *args, **kwargs):
        """Close database session after task completes"""
        db.session.remove()


@celery.task(base=CampaignTask, bind=True)
def bulk_send_campaign(self, campaign_id):
    """
    Background task: Send bulk emails for campaign
    
    This runs INDEPENDENTLY of web server - user can close browser
    and campaign will continue running.
    
    Args:
        campaign_id: Campaign ID to process
    """
    logger.info(f"Starting campaign {campaign_id}")
    
    try:
        campaign = Campaign.query.get(campaign_id)
        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            return
        
        # Update status
        campaign.status = 'running'
        campaign.started_at = datetime.utcnow()
        db.session.commit()
        
        # Emit real-time update
        emit_campaign_update(campaign_id, {
            'status': 'running',
            'message': 'Campaign started'
        })
        
        # Main sending loop
        while campaign.status == 'running':
            # Re-query to get latest status (user might have paused/stopped)
            db.session.refresh(campaign)
            
            if campaign.status == 'paused':
                logger.info(f"Campaign {campaign_id} paused, waiting...")
                time.sleep(5)
                continue
            
            if campaign.status in ['stopped', 'completed']:
                logger.info(f"Campaign {campaign_id} {campaign.status}")
                break
            
            # Get next unsent recipient
            recipient = get_next_recipient(campaign_id)
            if not recipient:
                # No more recipients
                logger.info(f"Campaign {campaign_id} completed - no more recipients")
                campaign.status = 'completed'
                campaign.completed_at = datetime.utcnow()
                db.session.commit()
                
                emit_campaign_update(campaign_id, {
                    'status': 'completed',
                    'message': 'All emails sent'
                })
                break
            
            # Get next SMTP (thread-safe rotation)
            smtp, smtp_key = get_next_smtp_with_lock(campaign_id)
            if not smtp:
                logger.error(f"Campaign {campaign_id} - No SMTP servers available")
                campaign.status = 'failed'
                campaign.error = 'No available SMTP servers'
                db.session.commit()
                
                emit_campaign_update(campaign_id, {
                    'status': 'failed',
                    'message': 'No SMTP servers available'
                })
                break
            
            # Get next FROM address (rotation)
            from_address = get_next_from_address(campaign_id)
            if not from_address:
                logger.error(f"Campaign {campaign_id} - No FROM addresses available")
                campaign.status = 'failed'
                campaign.error = 'No FROM addresses'
                db.session.commit()
                break
            
            # Send email with retry logic
            success = send_single_email_with_retry(
                campaign=campaign,
                recipient=recipient,
                smtp=smtp,
                smtp_key=smtp_key,
                from_address=from_address
            )
            
            if success:
                # Mark recipient as sent
                recipient.status = 'sent'
                recipient.sent_at = datetime.utcnow()
                
                # Update campaign stats
                campaign.emails_sent = (campaign.emails_sent or 0) + 1
                
                # Emit progress update
                emit_progress_update(campaign_id)
            
            db.session.commit()
            
            # Sleep between emails
            time.sleep(campaign.sleep_interval or 1.0)
        
        logger.info(f"Campaign {campaign_id} finished with status: {campaign.status}")
        
    except Exception as e:
        logger.error(f"Campaign {campaign_id} error: {str(e)}", exc_info=True)
        
        try:
            campaign = Campaign.query.get(campaign_id)
            campaign.status = 'failed'
            campaign.error = str(e)
            db.session.commit()
            
            emit_campaign_update(campaign_id, {
                'status': 'failed',
                'message': f'Error: {str(e)}'
            })
        except:
            pass


def get_next_recipient(campaign_id):
    """
    Get next unsent recipient for campaign
    
    Returns:
        Recipient object or None if all sent
    """
    return Recipient.query.filter(
        and_(
            Recipient.campaign_id == campaign_id,
            Recipient.status == 'pending'
        )
    ).first()


def get_next_smtp_with_lock(campaign_id):
    """
    Get next available SMTP server with thread-safe rotation
    Ported from smtp_manager.py
    
    Uses Redis lock to ensure thread-safety across multiple workers
    
    Returns:
        tuple: (SMTPServer object, server_key string) or (None, None)
    """
    from tasks.celery_app import redis_client
    
    campaign = Campaign.query.get(campaign_id)
    if not campaign or not campaign.smtp_servers:
        return None, None
    
    lock_key = f'campaign:{campaign_id}:smtp_lock'
    
    # Acquire Redis lock (thread-safe across workers!)
    with redis_client.lock(lock_key, timeout=10):
        smtps = campaign.smtp_servers
        index = campaign.smtp_index or 0
        attempts = 0
        
        while attempts < len(smtps):
            smtp = smtps[index % len(smtps)]
            server_key = f"{smtp.host}:{smtp.port}:{smtp.username}"
            
            # Check if server hasn't failed too many times
            if smtp.failures < 10:  # Max 10 failures before permanent disable
                # Update index for next rotation
                campaign.smtp_index = (index + 1) % len(smtps)
                db.session.commit()
                return smtp, server_key
            
            index += 1
            attempts += 1
        
        # All SMTPs failed
        return None, None


def get_next_from_address(campaign_id):
    """
    Get next FROM address with rotation
    
    Returns:
        FromAddress object or None
    """
    campaign = Campaign.query.get(campaign_id)
    if not campaign or not campaign.from_addresses:
        return None
    
    # Filter for verified addresses only
    verified_froms = [f for f in campaign.from_addresses if f.status == 'verified']
    
    if not verified_froms:
        # Fallback to all addresses
        verified_froms = campaign.from_addresses
    
    if not verified_froms:
        return None
    
    # Simple rotation based on campaign index
    index = campaign.from_index or 0
    from_address = verified_froms[index % len(verified_froms)]
    
    # Update index
    campaign.from_index = (index + 1) % len(verified_froms)
    db.session.commit()
    
    return from_address


def send_single_email_with_retry(campaign, recipient, smtp, smtp_key, from_address, max_retries=3):
    """
    Send single email with retry logic
    Ported from sending_manager.py
    
    If SMTP fails, tries different SMTP servers (rotation)
    
    Args:
        campaign: Campaign object
        recipient: Recipient object
        smtp: SMTPServer object
        smtp_key: Server identification string
        from_address: FromAddress object
        max_retries: Maximum retry attempts
        
    Returns:
        bool: True if sent successfully
    """
    for attempt in range(max_retries):
        try:
            # Decrypt password
            smtp_password = decrypt_password(smtp.password_encrypted)
            
            # Connect to SMTP
            server = smtplib.SMTP(smtp.host, smtp.port, timeout=30)
            
            try:
                server.starttls()
            except:
                pass  # Some servers don't support TLS
            
            server.login(smtp.username, smtp_password)
            
            # Build email message
            msg = MIMEMultipart("alternative")
            msg['From'] = f'{from_address.display_name or "Team"} <{from_address.email}>'
            msg['To'] = recipient.email
            msg['Subject'] = personalize_subject(campaign.subject, recipient, from_address)
            msg['Date'] = email.utils.formatdate(localtime=True)
            msg['Message-ID'] = email.utils.make_msgid()
            
            # Personalize template
            html_content = personalize_template(
                campaign.template,
                recipient,
                from_address
            )
            
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send
            server.send_message(msg)
            server.quit()
            
            # Mark SMTP as successful
            mark_smtp_success(smtp.id, smtp_key)
            
            # Log success
            log_email(
                campaign_id=campaign.id,
                recipient_email=recipient.email,
                from_email=from_address.email,
                smtp_used=smtp_key,
                status='sent',
                error=None
            )
            
            logger.info(f"Sent: {from_address.email} → {recipient.email} via {smtp_key}")
            
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP auth failed ({smtp_key}): {str(e)}")
            mark_smtp_failed(smtp.id, smtp_key, 'auth_failed')
            
            # Try different SMTP on next attempt
            if attempt < max_retries - 1:
                smtp, smtp_key = get_next_smtp_with_lock(campaign.id)
                if not smtp:
                    break
                continue
            
        except (smtplib.SMTPException, OSError, TimeoutError) as e:
            logger.error(f"SMTP error ({smtp_key}): {str(e)}")
            mark_smtp_failed(smtp.id, smtp_key, 'connection_failed')
            
            # Try different SMTP on next attempt
            if attempt < max_retries - 1:
                smtp, smtp_key = get_next_smtp_with_lock(campaign.id)
                if not smtp:
                    break
                continue
        
        except Exception as e:
            logger.error(f"Unexpected error sending email: {str(e)}", exc_info=True)
            break
    
    # All retries exhausted
    log_email(
        campaign_id=campaign.id,
        recipient_email=recipient.email,
        from_email=from_address.email,
        smtp_used=smtp_key,
        status='failed',
        error='Max retries exhausted'
    )
    
    recipient.status = 'failed'
    recipient.error = 'Failed after retries'
    campaign.emails_failed = (campaign.emails_failed or 0) + 1
    db.session.commit()
    
    return False


def mark_smtp_success(smtp_id, server_key):
    """
    Mark SMTP server as successful
    Reset failure counter after consecutive successes
    """
    from tasks.celery_app import redis_client
    
    smtp = SMTPServer.query.get(smtp_id)
    if not smtp:
        return
    
    # Increment success counter
    smtp.successes = (smtp.successes or 0) + 1
    smtp.last_used = datetime.utcnow()
    
    # Track consecutive successes in Redis
    success_key = f'smtp:{server_key}:consecutive_success'
    consecutive = redis_client.incr(success_key)
    redis_client.expire(success_key, 3600)  # 1 hour TTL
    
    # Reset failures after 3 consecutive successes
    if consecutive >= 3 and smtp.failures > 0:
        smtp.failures = max(0, smtp.failures - 1)
        redis_client.delete(success_key)
        logger.info(f"SMTP {server_key} failure count reduced to {smtp.failures}")
    
    db.session.commit()


def mark_smtp_failed(smtp_id, server_key, reason):
    """
    Mark SMTP server as failed
    Auto-disable after 10 failures
    """
    from tasks.celery_app import redis_client
    
    smtp = SMTPServer.query.get(smtp_id)
    if not smtp:
        return
    
    smtp.failures = (smtp.failures or 0) + 1
    smtp.last_error = reason
    smtp.last_error_at = datetime.utcnow()
    
    # Reset consecutive success counter
    redis_client.delete(f'smtp:{server_key}:consecutive_success')
    
    if smtp.failures >= 10:
        smtp.status = 'disabled'
        logger.warning(f"SMTP {server_key} DISABLED after {smtp.failures} failures")
    
    db.session.commit()


def log_email(campaign_id, recipient_email, from_email, smtp_used, status, error):
    """Log email send attempt"""
    log = EmailLog(
        campaign_id=campaign_id,
        recipient_email=recipient_email,
        from_email=from_email,
        smtp_used=smtp_used,
        status=status,
        error=error,
        sent_at=datetime.utcnow()
    )
    db.session.add(log)
    db.session.commit()


def personalize_template(template, recipient, from_address):
    """
    Personalize email template with variables
    Ported from sending_manager.py
    
    Supported variables:
        {RECIPIENT} - Recipient email
        {NAME} - Sender display name
        {DATE} - Current date
        {TIME} - Current time
        {RAND:min-max} - Random number in range
    """
    result = template
    
    # Basic replacements
    result = result.replace('{RECIPIENT}', recipient.email)
    result = result.replace('{NAME}', from_address.display_name or 'Team')
    result = result.replace('{DATE}', datetime.now().strftime('%B %d, %Y'))
    result = result.replace('{TIME}', datetime.now().strftime('%I:%M %p'))
    
    # Random number tags
    result = re.sub(
        r'\{RAND:(\d+)-(\d+)\}',
        lambda m: str(random.randint(int(m.group(1)), int(m.group(2)))),
        result
    )
    
    return result


def personalize_subject(subject, recipient, from_address):
    """Personalize email subject"""
    if not subject:
        return "Important Message"
    
    result = subject
    result = result.replace('{RECIPIENT}', recipient.email.split('@')[0])
    result = result.replace('{NAME}', from_address.display_name or 'Team')
    result = result.replace('{DATE}', datetime.now().strftime('%B %d, %Y'))
    
    # Random number
    result = re.sub(
        r'\{RAND:(\d+)-(\d+)\}',
        lambda m: str(random.randint(int(m.group(1)), int(m.group(2)))),
        result
    )
    
    return result


def emit_campaign_update(campaign_id, data):
    """
    Emit campaign status update via Redis pub/sub
    Flask will forward to WebSocket clients
    """
    from tasks.celery_app import redis_client
    import json
    
    redis_client.publish(
        f'campaign:{campaign_id}:updates',
        json.dumps({
            **data,
            'timestamp': datetime.utcnow().isoformat()
        })
    )


def emit_progress_update(campaign_id):
    """Emit progress statistics update"""
    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return
    
    total = campaign.recipients.count()
    sent = campaign.emails_sent or 0
    failed = campaign.emails_failed or 0
    pending = total - sent - failed
    progress = (sent / total * 100) if total > 0 else 0
    
    emit_campaign_update(campaign_id, {
        'type': 'progress',
        'sent': sent,
        'failed': failed,
        'pending': pending,
        'total': total,
        'progress': round(progress, 2)
    })


@celery.task(base=CampaignTask)
def pause_campaign(campaign_id):
    """Pause running campaign"""
    campaign = Campaign.query.get(campaign_id)
    if campaign and campaign.status == 'running':
        campaign.status = 'paused'
        db.session.commit()
        
        emit_campaign_update(campaign_id, {
            'status': 'paused',
            'message': 'Campaign paused'
        })
        
        logger.info(f"Campaign {campaign_id} paused")


@celery.task(base=CampaignTask)
def resume_campaign(campaign_id):
    """Resume paused campaign"""
    campaign = Campaign.query.get(campaign_id)
    if campaign and campaign.status == 'paused':
        campaign.status = 'running'
        db.session.commit()
        
        emit_campaign_update(campaign_id, {
            'status': 'running',
            'message': 'Campaign resumed'
        })
        
        logger.info(f"Campaign {campaign_id} resumed")


@celery.task(base=CampaignTask)
def stop_campaign(campaign_id):
    """Stop running campaign"""
    campaign = Campaign.query.get(campaign_id)
    if campaign and campaign.status in ['running', 'paused']:
        campaign.status = 'stopped'
        campaign.stopped_at = datetime.utcnow()
        db.session.commit()
        
        emit_campaign_update(campaign_id, {
            'status': 'stopped',
            'message': 'Campaign stopped by user'
        })
        
        logger.info(f"Campaign {campaign_id} stopped")
