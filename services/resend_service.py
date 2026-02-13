"""
Resend Email Service
Modern email sending using Resend API
"""
import os
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class ResendEmailService:
    """Email service using Resend API"""
    
    def __init__(self):
        self.api_key = os.getenv('RESEND_API_KEY')
        self.default_sender = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('RESEND_DEFAULT_SENDER'))
        
        if not self.api_key:
            logger.warning("RESEND_API_KEY not configured - emails will be mocked")
    
    def send_email(self, to: str, subject: str, html: str = None, text: str = None, from_email: str = None) -> dict:
        """
        Send email using Resend API
        
        Args:
            to: Recipient email address
            subject: Email subject
            html: HTML body content
            text: Plain text body content
            from_email: Sender email (defaults to configured default sender)
        
        Returns:
            dict with status and message_id or error
        """
        if not self.api_key:
            logger.warning(f"Mock email sent to {to}: {subject}")
            return {
                'status': 'mocked',
                'message': f'Resend API key not configured. Email would be sent to: {to}',
                'subject': subject
            }
        
        try:
            import resend
            
            resend.api_key = self.api_key
            
            # Use default sender if not specified
            sender = from_email or self.default_sender
            
            if not sender:
                logger.error("No sender email configured")
                return {'status': 'error', 'error': 'No sender email configured'}
            
            params = {
                'from': sender,
                'to': to,
                'subject': subject,
            }
            
            # Add HTML or text body
            if html:
                params['html'] = html
            elif text:
                params['text'] = text
            
            response = resend.Emails.send(params)
            
            logger.info(f"Email sent successfully to {to}: {response.get('id')}")
            return {
                'status': 'sent',
                'message_id': response.get('id')
            }
            
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def send_email_batch(self, emails: List[dict]) -> dict:
        """
        Send multiple emails in batch
        
        Args:
            emails: List of dicts with 'to', 'subject', 'html', 'text' keys
        
        Returns:
            dict with status and count
        """
        if not self.api_key:
            logger.warning(f"Mock batch email: {len(emails)} emails would be sent")
            return {'status': 'mocked', 'count': len(emails)}
        
        sent_count = 0
        errors = []
        
        for email in emails:
            result = self.send_email(
                to=email.get('to'),
                subject=email.get('subject'),
                html=email.get('html'),
                text=email.get('text'),
                from_email=email.get('from')
            )
            
            if result.get('status') == 'sent':
                sent_count += 1
            else:
                errors.append(result.get('error'))
        
        return {
            'status': 'completed',
            'sent': sent_count,
            'failed': len(errors),
            'errors': errors
        }


def get_email_service():
    """Factory function to get email service instance"""
    return ResendEmailService()


# Helper function for backward compatibility with Flask-Mail Message
def send_email_via_resend(to: str, subject: str, body: str, html: str = None, sender: str = None) -> dict:
    """
    Helper function to send email (compatible with Flask-Mail Message usage)
    
    Usage:
        from services.resend_service import send_email_via_resend
        send_email_via_resend(
            to="user@example.com",
            subject="Subject",
            body="Plain text body",
            html="<p>HTML body</p>",
            sender="sender@example.com"
        )
    """
    service = get_email_service()
    return service.send_email(
        to=to,
        subject=subject,
        html=html,
        text=body,
        from_email=sender
    )
