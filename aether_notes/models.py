import datetime

from django.db import models
from django.utils import timezone
from django.conf import settings


# Create your models here.
class Note(models.Model):
    text = models.TextField()
    pub_date = models.DateTimeField("date published", db_index=True)
    author = models.CharField(max_length=25, null=True, blank=True)
    # If authored by a registered user (optional)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="notes")
    # Denormalized count of unique device "witnesses". Updated via NoteView.
    views = models.PositiveIntegerField(default=0)
    # Denormalized count of user flags (unique per device). Updated via NoteFlag.
    flags = models.PositiveIntegerField(default=0)
    # Device that created the note (client-generated UUID). Used for delete authorization.
    created_device_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    # Draft support
    is_draft = models.BooleanField(default=False, db_index=True)
    last_modified = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.text

    def was_published_recently(self):
        return self.pub_date >= timezone.now() - datetime.timedelta(days=1)


class NoteView(models.Model):
    """Unique record that a device has seen a note.

    We don't track users; instead, store a random device_id string (UUID) provided by the client.
    """
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="note_views")
    device_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["note", "device_id"], name="unique_note_device_view"),
        ]
        indexes = [
            models.Index(fields=["device_id", "created_at"]),
        ]

class NoteFlag(models.Model):
    """Unique record that a device has flagged a note."""
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="note_flags")
    device_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["note", "device_id"], name="unique_note_device_flag"),
        ]
        indexes = [
            models.Index(fields=["device_id", "created_at"]),
        ]


class NoteCrosspost(models.Model):
    """Stores metadata about a note cross-posted to an external network.

    We persist enough information to render a link later even if the user changes
    their instance / handle. Status is simple for now (success/error) and can be
    expanded with retry metadata later.
    """
    NETWORK_CHOICES = [
        ("mastodon", "Mastodon"),
        ("bluesky", "Bluesky"),
    ]

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="crossposts")
    network = models.CharField(max_length=20, choices=NETWORK_CHOICES)
    remote_id = models.CharField(max_length=200, blank=True)  # e.g. status ID or URI
    remote_url = models.URLField(max_length=500, blank=True)  # canonical URL to view
    # Legacy fields (status/error) retained; now a row's existence implies success.
    status = models.CharField(max_length=20, default="success", db_index=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["note", "network"], name="unique_note_network_crosspost"),
        ]
        indexes = [
            models.Index(fields=["network", "status"]),
        ]

    def mark_success(self, remote_id: str | None = None, remote_url: str | None = None):  # pragma: no cover - trivial
        if remote_id:
            self.remote_id = remote_id
        if remote_url:
            self.remote_url = remote_url
        self.status = "success"
        self.error = ""
        self.save(update_fields=["remote_id", "remote_url", "status", "error", "updated_at"])

    def mark_error(self, message: str):  # retained for backward compatibility (unused now)
        self.status = "error"
        self.error = (message or "")[:300]
        self.save(update_fields=["status", "error", "updated_at"])

    def __str__(self) -> str:  # pragma: no cover - trivial
        nid = getattr(self.note, 'id', None)
        return f"NoteCrosspost(note={nid}, network={self.network}, status={self.status})"
