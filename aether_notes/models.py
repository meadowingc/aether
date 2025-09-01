import datetime

from django.db import models
from django.utils import timezone


# Create your models here.
class Note(models.Model):
    text = models.TextField()
    pub_date = models.DateTimeField("date published", db_index=True)
    author = models.CharField(max_length=100, null=True, blank=True)
    # Denormalized count of unique device "witnesses". Updated via NoteView.
    views = models.PositiveIntegerField(default=0)
    # Device that created the note (client-generated UUID). Used for delete authorization.
    created_device_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)

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
