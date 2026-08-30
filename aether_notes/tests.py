import datetime
import io
import tempfile
from unittest.mock import patch

from PIL import Image

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .management.commands.publish_queued_notes import Command
from .models import Note, PostQueueSettings, QueuedNote


User = get_user_model()


def make_note(user, text, *, is_draft=True):
    return Note.objects.create(
        text=text,
        author=user.username,
        user=user,
        pub_date=timezone.now(),
        is_draft=is_draft,
    )


def make_queue_entry(user, text, position):
    return QueuedNote.objects.create(
        note=make_note(user, text),
        user=user,
        position=position,
    )


class QueueModelTests(TestCase):
    def test_interval_delta_uses_selected_unit(self):
        user = User.objects.create_user(username="model-user", password="pw")
        queue_settings = PostQueueSettings(user=user, interval_value=3)
        self.assertEqual(queue_settings.interval_delta(), datetime.timedelta(hours=3))
        queue_settings.interval_unit = PostQueueSettings.UNIT_DAYS
        self.assertEqual(queue_settings.interval_delta(), datetime.timedelta(days=3))

    def test_queue_positions_are_unique_per_user(self):
        user = User.objects.create_user(username="unique-user", password="pw")
        make_queue_entry(user, "first", 1)
        with self.assertRaises(IntegrityError):
            make_queue_entry(user, "duplicate", 1)


class QueueViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="queue-user", password="pw")
        self.client.force_login(self.user)

    def test_add_to_queue_persists_choices_and_schedules_first_item(self):
        before = timezone.now() + datetime.timedelta(hours=24)
        response = self.client.post(
            reverse("create_note"),
            {
                "text": "queued",
                "add_queue": "1",
                "xp_mastodon": "on",
                "xp_tumblr": "on",
            },
        )

        self.assertRedirects(response, reverse("queue_list"))
        entry = QueuedNote.objects.get(user=self.user)
        self.assertTrue(entry.note.is_draft)
        self.assertTrue(entry.crosspost_mastodon)
        self.assertTrue(entry.crosspost_tumblr)
        self.assertFalse(entry.crosspost_bluesky)
        queue_settings = PostQueueSettings.objects.get(user=self.user)
        self.assertGreaterEqual(queue_settings.next_publish_at, before)

    def test_queued_note_is_hidden_from_feed_archive_and_drafts(self):
        self.user.profile.show_archive = True
        self.user.profile.save()
        entry = make_queue_entry(self.user, "secret queued text", 1)

        self.assertNotContains(self.client.get(reverse("index")), "secret queued text")
        self.assertNotContains(
            self.client.get(
                reverse("accounts:user_archive", args=[self.user.username])
            ),
            "secret queued text",
        )
        self.assertNotContains(
            self.client.get(reverse("drafts_list")),
            "secret queued text",
        )
        self.assertEqual(
            self.client.get(reverse("edit_draft", args=[entry.note_id])).status_code,
            404,
        )

    def test_interval_pause_and_resume_restart_countdown(self):
        make_queue_entry(self.user, "first", 1)
        queue_settings = PostQueueSettings.objects.create(user=self.user)

        response = self.client.post(
            reverse("update_queue_settings"),
            {"interval_value": "2", "interval_unit": "days"},
        )
        self.assertRedirects(response, reverse("queue_list"))
        queue_settings.refresh_from_db()
        self.assertEqual(queue_settings.interval_value, 2)
        self.assertEqual(queue_settings.interval_unit, "days")
        self.assertIsNotNone(queue_settings.next_publish_at)

        self.client.post(reverse("toggle_queue"))
        queue_settings.refresh_from_db()
        self.assertTrue(queue_settings.paused)
        self.assertIsNone(queue_settings.next_publish_at)

        resume_before = timezone.now() + datetime.timedelta(days=2)
        self.client.post(reverse("toggle_queue"))
        queue_settings.refresh_from_db()
        self.assertFalse(queue_settings.paused)
        self.assertGreaterEqual(queue_settings.next_publish_at, resume_before)

    def test_edit_reorder_and_delete_queue_items(self):
        first = make_queue_entry(self.user, "first", 1)
        second = make_queue_entry(self.user, "second", 2)
        PostQueueSettings.objects.create(
            user=self.user,
            next_publish_at=timezone.now() + datetime.timedelta(hours=24),
        )

        self.client.post(
            reverse("edit_queue_item", args=[second.pk]),
            {"text": "second edited", "xp_bluesky": "on"},
        )
        second.refresh_from_db()
        self.assertEqual(second.note.text, "second edited")
        self.assertTrue(second.crosspost_bluesky)

        self.client.post(
            reverse("move_queue_item", args=[second.pk, "up"]),
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((second.position, first.position), (1, 2))

        self.client.post(reverse("delete_queue_item", args=[second.pk]))
        first.refresh_from_db()
        self.assertEqual(first.position, 1)
        self.client.post(reverse("delete_queue_item", args=[first.pk]))
        self.assertIsNone(
            PostQueueSettings.objects.get(user=self.user).next_publish_at
        )

    def test_queue_routes_are_scoped_to_owner(self):
        other = User.objects.create_user(username="other-user", password="pw")
        entry = make_queue_entry(other, "not yours", 1)
        self.assertEqual(
            self.client.get(reverse("edit_queue_item", args=[entry.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse("delete_queue_item", args=[entry.pk])).status_code,
            404,
        )
        self.assertTrue(QueuedNote.objects.filter(pk=entry.pk).exists())

    def test_anonymous_user_cannot_queue(self):
        self.client.logout()
        response = self.client.post(
            reverse("create_note"),
            {"text": "anonymous queue", "add_queue": "1"},
        )
        self.assertRedirects(response, reverse("index"))
        self.assertFalse(QueuedNote.objects.exists())
        self.assertFalse(Note.objects.exists())

    def test_queue_rejects_author_longer_than_note_field(self):
        long_username = "q" * 26
        user = User.objects.create_user(username=long_username, password="test-password")
        self.client.force_login(user)

        response = self.client.post(
            reverse("create_note"),
            {"text": "invalid queued note", "add_queue": "1"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"ok": False, "error": "author_too_long"})
        self.assertFalse(Note.objects.filter(user=user).exists())
        self.assertFalse(QueuedNote.objects.filter(user=user).exists())
        self.assertFalse(PostQueueSettings.objects.filter(user=user).exists())

    def test_generic_note_deletion_repairs_queue_state(self):
        first = make_queue_entry(self.user, "first", 1)
        second = make_queue_entry(self.user, "second", 2)
        queue_settings = PostQueueSettings.objects.create(
            user=self.user,
            next_publish_at=timezone.now() + datetime.timedelta(hours=24),
        )

        response = self.client.post(
            reverse("delete_note"),
            {"note_id": first.note_id, "device_id": "authenticated-user"},
        )

        self.assertEqual(response.status_code, 200)
        second.refresh_from_db()
        self.assertEqual(second.position, 1)
        self.assertIsNotNone(queue_settings.next_publish_at)

        response = self.client.post(
            reverse("delete_note"),
            {"note_id": second.note_id, "device_id": "authenticated-user"},
        )

        self.assertEqual(response.status_code, 200)
        queue_settings.refresh_from_db()
        self.assertIsNone(queue_settings.next_publish_at)

    def test_immediate_posts_and_drafts_still_work(self):
        self.client.post(reverse("create_note"), {"text": "immediate"})
        immediate = Note.objects.get(text="immediate")
        self.assertFalse(immediate.is_draft)

        self.client.post(
            reverse("create_note"),
            {"text": "draft", "save_draft": "1"},
        )
        draft = Note.objects.get(text="draft")
        self.assertTrue(draft.is_draft)
        self.assertFalse(hasattr(draft, "queue_entry"))


class QueueRunnerTests(TransactionTestCase):
    reset_sequences = True

    def _due_queue(self, username, texts):
        user = User.objects.create_user(username=username, password="pw")
        settings = PostQueueSettings.objects.create(
            user=user,
            interval_value=2,
            interval_unit="hours",
            next_publish_at=timezone.now() - datetime.timedelta(minutes=1),
        )
        entries = [
            make_queue_entry(user, text, position)
            for position, text in enumerate(texts, start=1)
        ]
        return user, settings, entries

    def test_runner_publishes_only_first_due_item_and_compacts_queue(self):
        user, settings, entries = self._due_queue("runner-user", ["one", "two"])
        before = timezone.now()

        call_command("publish_queued_notes", verbosity=0)

        entries[0].note.refresh_from_db()
        entries[1].note.refresh_from_db()
        self.assertFalse(entries[0].note.is_draft)
        self.assertGreaterEqual(entries[0].note.pub_date, before)
        self.assertTrue(entries[1].note.is_draft)
        remaining = QueuedNote.objects.get(user=user)
        self.assertEqual(remaining.position, 1)
        settings.refresh_from_db()
        self.assertGreaterEqual(
            settings.next_publish_at,
            before + datetime.timedelta(hours=2),
        )

    def test_runner_clears_schedule_after_last_item(self):
        _, settings, entries = self._due_queue("last-user", ["last"])
        call_command("publish_queued_notes", verbosity=0)
        settings.refresh_from_db()
        entries[0].note.refresh_from_db()
        self.assertFalse(entries[0].note.is_draft)
        self.assertIsNone(settings.next_publish_at)

    def test_runner_ignores_paused_and_future_queues(self):
        _, paused, paused_entries = self._due_queue("paused-user", ["paused"])
        paused.paused = True
        paused.save()
        _, future, future_entries = self._due_queue("future-user", ["future"])
        future.next_publish_at = timezone.now() + datetime.timedelta(hours=1)
        future.save()

        call_command("publish_queued_notes", verbosity=0)

        paused_entries[0].note.refresh_from_db()
        future_entries[0].note.refresh_from_db()
        self.assertTrue(paused_entries[0].note.is_draft)
        self.assertTrue(future_entries[0].note.is_draft)

    def test_claim_prevents_same_due_slot_from_publishing_twice(self):
        _, settings, entries = self._due_queue("claim-user", ["one", "two"])
        expected = settings.next_publish_at
        command = Command()

        self.assertTrue(command._publish_due_queue(settings.pk, expected, timezone.now()))
        self.assertFalse(command._publish_due_queue(settings.pk, expected, timezone.now()))
        entries[1].note.refresh_from_db()
        self.assertTrue(entries[1].note.is_draft)

    def test_crosspost_exception_does_not_block_other_queues(self):
        _, _, first_entries = self._due_queue("error-user", ["error item"])
        _, _, second_entries = self._due_queue("next-user", ["next item"])
        first_entry = first_entries[0]
        first_entry.crosspost_mastodon = True
        first_entry.save()

        with patch(
            "aether_notes.services.post_selected_networks",
            side_effect=RuntimeError("remote failed"),
        ):
            call_command("publish_queued_notes", verbosity=0)

        first_entry.note.refresh_from_db()
        second_entries[0].note.refresh_from_db()
        self.assertFalse(first_entry.note.is_draft)
        self.assertFalse(second_entries[0].note.is_draft)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_runner_publishes_stored_image_and_removes_hq_copy(self):
        user, _, entries = self._due_queue("image-user", [])
        image = Image.new("RGB", (4, 4), "red")
        raw = io.BytesIO()
        image.save(raw, format="PNG")
        upload = SimpleUploadedFile("test.png", raw.getvalue(), "image/png")
        response_client = self.client
        response_client.force_login(user)
        response_client.post(
            reverse("create_note"),
            {"text": "image queued", "add_queue": "1", "image": upload},
        )
        settings = PostQueueSettings.objects.get(user=user)
        settings.next_publish_at = timezone.now() - datetime.timedelta(minutes=1)
        settings.save()
        note = Note.objects.get(text="image queued")
        self.assertTrue(note.image_hq)

        call_command("publish_queued_notes", verbosity=0)

        note.refresh_from_db()
        self.assertFalse(note.is_draft)
        self.assertTrue(note.image)
        self.assertFalse(note.image_hq)
