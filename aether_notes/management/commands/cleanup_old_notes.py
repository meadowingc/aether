"""Management command to delete notes older than the ephemeral window (7 days).

Also cleans up associated image files on disk via the post_delete signal.
Usage: python manage.py cleanup_old_notes [--days 7] [--dry-run]
"""

import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from aether_notes.models import Note


class Command(BaseCommand):
    help = "Delete published notes older than N days (default 7) and their images."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Delete notes older than this many days (default: 7).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        cutoff = timezone.now() - datetime.timedelta(days=days)

        qs = Note.objects.filter(pub_date__lt=cutoff, is_draft=False)
        count = qs.count()

        if dry_run:
            self.stdout.write(f"[DRY RUN] Would delete {count} note(s) older than {days} days.")
            return

        # Delete one-by-one to trigger post_delete signal for image cleanup
        deleted = 0
        for note in qs.iterator():
            note.delete()
            deleted += 1

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} note(s) older than {days} days."))
