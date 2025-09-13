from __future__ import annotations
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile

User = get_user_model()

@receiver(post_save, sender=User)
def create_profile_for_new_user(sender, instance: User, created: bool, **kwargs):
    if created:
        Profile.objects.create(user=instance)
