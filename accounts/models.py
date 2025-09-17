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

    # Status.cafe (HTML form scraping integration)
    status_cafe_username = models.CharField(max_length=100, blank=True)
    status_cafe_password = EncryptedTextField(blank=True)
    status_cafe_default_face = models.CharField(
        max_length=8,
        blank=True,
        help_text="Optional default emoji code to use when cross‑posting (e.g. 🙂)",
    )

    # Preferences
    crosspost_mastodon = models.BooleanField(default=False)
    crosspost_bluesky = models.BooleanField(default=False)
    crosspost_status_cafe = models.BooleanField(default=False)

    # Archive / profile page (optional). If enabled, show user's notes beyond ephemeral window.
    show_archive = models.BooleanField(default=False, help_text="If true, a public archive/profile page is enabled")
    bio = models.TextField(blank=True, help_text="Optional short bio displayed on your archive page")

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
