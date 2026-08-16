from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from aether_notes.models import PostQueueSettings, QueuedNote
from aether_notes.services import CrosspostSelection, publish_note


class Command(BaseCommand):
    help = "Publish due notes from active user queues."

    def handle(self, *args, **options):
        now = timezone.now()
        due = list(
            PostQueueSettings.objects.filter(
                paused=False,
                next_publish_at__lte=now,
            ).values_list("pk", "next_publish_at")
        )
        published = 0

        for settings_id, expected_time in due:
            try:
                did_publish = self._publish_due_queue(
                    settings_id,
                    expected_time,
                    now,
                )
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(
                        f"Queue {settings_id} failed: {exc.__class__.__name__}"
                    )
                )
                continue
            if did_publish:
                published += 1

        self.stdout.write(self.style.SUCCESS(f"Published {published} queued note(s)."))

    def _publish_due_queue(self, settings_id, expected_time, now):
        with transaction.atomic():
            queue_settings = PostQueueSettings.objects.select_related("user").get(
                pk=settings_id
            )
            claimed_until = now + queue_settings.interval_delta()
            claimed = PostQueueSettings.objects.filter(
                pk=settings_id,
                paused=False,
                next_publish_at=expected_time,
            ).update(next_publish_at=claimed_until)
            if not claimed:
                return False

            entry = (
                QueuedNote.objects.select_related("note")
                .filter(user=queue_settings.user)
                .order_by("position", "id")
                .first()
            )
            if entry is None:
                PostQueueSettings.objects.filter(pk=settings_id).update(
                    next_publish_at=None
                )
                return False

            note = entry.note
            selection = CrosspostSelection(
                mastodon=entry.crosspost_mastodon,
                bluesky=entry.crosspost_bluesky,
                status_cafe=entry.crosspost_status_cafe,
                tumblr=entry.crosspost_tumblr,
                piclog_blue=entry.crosspost_piclog_blue,
                status_cafe_face=entry.status_cafe_face or None,
            )
            removed_position = entry.position
            entry.delete()
            later_entries = QueuedNote.objects.filter(
                user=queue_settings.user,
                position__gt=removed_position,
            ).order_by("position")
            for later_entry in later_entries:
                later_entry.position -= 1
                later_entry.save(update_fields=["position"])

            if not QueuedNote.objects.filter(user=queue_settings.user).exists():
                PostQueueSettings.objects.filter(pk=settings_id).update(
                    next_publish_at=None
                )

            publish_note(
                note,
                user=queue_settings.user,
                selection=selection,
                async_crossposts=False,
            )
            self.stdout.write(f"Published queued note {note.pk}.")
            return True
