"""
Email adapter using Django's mail backend.
"""
import logging
import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from apps.core.ports import NotificationGateway, NotificationPayload, NotificationResult

logger = logging.getLogger(__name__)


class EmailAdapter(NotificationGateway):
    """
    Adapter: SMTP email sender using Django's mail backend.

    Uses EmailMultiAlternatives to support both plain text and HTML.
    """

    @property
    def channel_name(self) -> str:
        return "email"

    def send(self, payload: NotificationPayload) -> NotificationResult:
        """
        Send an email notification.

        Args:
            payload: Contains recipient email, subject, and body

        Returns:
            NotificationResult with success status
        """
        try:
            subject = payload.subject or "Notificación Ambacar"

            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body=payload.body,  # Plain text version
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[payload.recipient],
            )

            # If body contains HTML, add as alternative
            if self._is_html(payload.body):
                email.attach_alternative(payload.body, "text/html")

            # Send email
            email.send(fail_silently=False)

            logger.info(f"Email sent successfully to {payload.recipient}")

            return NotificationResult(
                success=True,
                message_id=None,  # Django doesn't return message ID by default
            )

        except Exception as e:
            logger.error(f"Failed to send email to {payload.recipient}: {str(e)}")
            return NotificationResult(
                success=False,
                error_message=str(e),
                error_code="EMAIL_SEND_FAILED",
            )

    def validate_recipient(self, recipient: str) -> bool:
        """
        Validate email address format.
        """
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(email_regex, recipient))

    def is_configured(self) -> bool:
        """
        Check if email is properly configured.
        """
        return bool(
            settings.EMAIL_HOST and
            settings.EMAIL_HOST_USER and
            settings.DEFAULT_FROM_EMAIL
        )

    def _is_html(self, content: str) -> bool:
        """Check if content contains HTML tags."""
        return bool(re.search(r"<[^>]+>", content))
