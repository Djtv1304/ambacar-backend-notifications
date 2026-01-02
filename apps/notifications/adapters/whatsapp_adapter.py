"""
WhatsApp adapter using Evolution API.
"""
import logging
import re

import requests
from django.conf import settings

from apps.core.ports import NotificationGateway, NotificationPayload, NotificationResult

logger = logging.getLogger(__name__)


class WhatsAppAdapter(NotificationGateway):
    """
    Adapter: WhatsApp sender via Evolution API.

    Evolution API is a self-hosted WhatsApp API solution.
    Documentation: https://doc.evolution-api.com/
    """

    @property
    def channel_name(self) -> str:
        return "whatsapp"

    def send(self, payload: NotificationPayload) -> NotificationResult:
        """
        Send a WhatsApp text message via Evolution API.

        Args:
            payload: Contains recipient phone number and message body

        Returns:
            NotificationResult with success status and message_id
        """
        if not self.is_configured():
            return NotificationResult(
                success=False,
                error_message="WhatsApp (Evolution API) is not configured",
                error_code="WHATSAPP_NOT_CONFIGURED",
            )

        url = f"{settings.EVOLUTION_API_URL}/message/sendText/{settings.EVOLUTION_INSTANCE}"

        headers = {
            "Content-Type": "application/json",
            "apikey": settings.EVOLUTION_API_KEY,
        }

        data = {
            "number": self._normalize_phone(payload.recipient),
            "text": payload.body,
        }

        try:
            response = requests.post(
                url,
                json=data,
                headers=headers,
                timeout=settings.EVOLUTION_TIMEOUT,
            )
            response.raise_for_status()

            result = response.json()
            message_id = result.get("key", {}).get("id")

            logger.info(f"WhatsApp sent to {payload.recipient}, message_id: {message_id}")

            return NotificationResult(
                success=True,
                message_id=message_id,
                raw_response=result,
            )

        except requests.exceptions.Timeout:
            logger.error(f"WhatsApp API timeout for {payload.recipient}")
            return NotificationResult(
                success=False,
                error_message="WhatsApp API timeout",
                error_code="WHATSAPP_TIMEOUT",
            )

        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_detail = e.response.json()
            except Exception:
                error_detail = e.response.text

            logger.error(f"WhatsApp API HTTP error: {error_detail}")
            return NotificationResult(
                success=False,
                error_message=f"HTTP Error: {str(e)}",
                error_code="WHATSAPP_HTTP_ERROR",
                raw_response=error_detail,
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"WhatsApp API request error: {str(e)}")
            return NotificationResult(
                success=False,
                error_message=str(e),
                error_code="WHATSAPP_API_ERROR",
            )

    def validate_recipient(self, recipient: str) -> bool:
        """
        Validate phone number format.
        Expects international format like +593987654321 or 593987654321
        """
        # Remove common formatting
        cleaned = re.sub(r"[\s\-\(\)\+]", "", recipient)
        # Should be 10-15 digits
        phone_regex = r"^\d{10,15}$"
        return bool(re.match(phone_regex, cleaned))

    def is_configured(self) -> bool:
        """
        Check if Evolution API is properly configured.
        """
        return bool(
            settings.EVOLUTION_API_URL and
            settings.EVOLUTION_API_KEY and
            settings.EVOLUTION_INSTANCE
        )

    def _normalize_phone(self, phone: str) -> str:
        """
        Normalize phone number for Evolution API.
        Removes spaces, dashes, parentheses.
        Removes leading + if present.
        """
        cleaned = re.sub(r"[\s\-\(\)]", "", phone)
        if cleaned.startswith("+"):
            cleaned = cleaned[1:]
        return cleaned
