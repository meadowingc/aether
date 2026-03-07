"""Signals for aether_notes app — image cleanup on Note deletion."""

import os

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Note


@receiver(post_delete, sender=Note)
def delete_note_image_file(sender, instance, **kwargs):
    """Remove the image file from disk when a Note is deleted."""
    if instance.image and instance.image.name:
        try:
            storage = instance.image.storage
            if storage.exists(instance.image.name):
                storage.delete(instance.image.name)
        except Exception:
            pass
