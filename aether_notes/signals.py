"""Signals for aether_notes app — image cleanup on Note deletion."""

import os

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Note


@receiver(post_delete, sender=Note)
def delete_note_image_file(sender, instance, **kwargs):
    """Remove the image files from disk when a Note is deleted."""
    for field in (instance.image, getattr(instance, "image_hq", None)):
        if field and field.name:
            try:
                storage = field.storage
                if storage.exists(field.name):
                    storage.delete(field.name)
            except Exception:
                pass
