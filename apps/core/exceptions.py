"""
Custom exceptions for the notification service.
"""


class NotificationServiceError(Exception):
    """Base exception for notification service errors."""
    pass


class ChannelNotConfiguredError(NotificationServiceError):
    """Raised when a notification channel is not properly configured."""
    pass


class TemplateRenderError(NotificationServiceError):
    """Raised when template rendering fails."""
    pass


class RecipientNotFoundError(NotificationServiceError):
    """Raised when the notification recipient cannot be found."""
    pass


class OrchestrationConfigNotFoundError(NotificationServiceError):
    """Raised when no orchestration config matches the event."""
    pass


class ChannelSendError(NotificationServiceError):
    """Raised when sending through a channel fails."""

    def __init__(self, channel: str, message: str, error_code: str = None):
        self.channel = channel
        self.error_code = error_code
        super().__init__(f"[{channel}] {message}")


class MaxRetriesExceededError(NotificationServiceError):
    """Raised when maximum retry attempts have been exceeded."""
    pass


class InvalidEventPayloadError(NotificationServiceError):
    """Raised when the event payload is invalid."""
    pass
