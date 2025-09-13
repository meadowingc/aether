from __future__ import annotations

from django.conf import settings
from django.db import models
from .fields import EncryptedTextField


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    website = models.URLField(blank=True)

    # Mastodon
    mastodon_instance = models.CharField(max_length=200, blank=True)
    mastodon_token = EncryptedTextField(blank=True)
    mastodon_char_limit = models.PositiveIntegerField(default=2000)

    # Bluesky
    bluesky_handle = models.CharField(max_length=100, blank=True)
    bluesky_app_password = EncryptedTextField(blank=True)

    # Preferences
    crosspost_mastodon = models.BooleanField(default=False)
    crosspost_bluesky = models.BooleanField(default=False)

    # Diagnostics (store only last error, optional)
    last_crosspost_error = models.TextField(blank=True)
    last_crosspost_error_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Profile({self.user.username})"

    def record_crosspost_error(self, message: str) -> None:
        from django.utils import timezone
        self.last_crosspost_error = (message or "")[:500]
        self.last_crosspost_error_at = timezone.now()
        self.save(update_fields=["last_crosspost_error", "last_crosspost_error_at"])

    def clear_crosspost_error(self) -> None:
        self.last_crosspost_error = ""
        self.last_crosspost_error_at = None
        self.save(update_fields=["last_crosspost_error", "last_crosspost_error_at"])
