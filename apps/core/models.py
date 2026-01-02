"""
Base models for the notification service.
"""
import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base model with creation and update timestamps.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """
    Abstract base model with UUID primary key.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    """
    Combined UUID + timestamps abstract model.
    Use this as the base for most models.
    """

    class Meta:
        abstract = True
