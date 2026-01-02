"""
Port (Interface) for notification gateways.
Each channel adapter implements this interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class NotificationPayload:
    """
    Standard payload for all notification channels.
    """
    recipient: str  # email, phone number, or customer_id for push
    body: str
    subject: Optional[str] = None  # For email
    metadata: dict = field(default_factory=dict)  # Channel-specific data


@dataclass
class NotificationResult:
    """
    Result of a notification send attempt.
    """
    success: bool
    message_id: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    raw_response: Optional[Any] = None


class NotificationGateway(ABC):
    """
    Port: Abstract interface for notification senders.
    Each channel (email, whatsapp, push) implements this.

    This follows the Hexagonal Architecture pattern:
    - Ports define the interface (this file)
    - Adapters implement the interface (in adapters/)
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Return the channel identifier (email, whatsapp, push)."""
        pass

    @abstractmethod
    def send(self, payload: NotificationPayload) -> NotificationResult:
        """
        Send a notification through this channel.

        Args:
            payload: The notification content and recipient

        Returns:
            NotificationResult with success status and optional message_id or error
        """
        pass

    @abstractmethod
    def validate_recipient(self, recipient: str) -> bool:
        """
        Validate that the recipient format is correct for this channel.

        Args:
            recipient: The recipient address/identifier

        Returns:
            True if valid, False otherwise
        """
        pass

    def is_configured(self) -> bool:
        """
        Check if this channel is properly configured.
        Override in subclasses that need configuration validation.

        Returns:
            True if configured, False otherwise
        """
        return True
