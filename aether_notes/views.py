import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import F, Max
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.utils import rate_limited

from .models import Note, NoteFlag, NoteView, PostQueueSettings, QueuedNote
from .services import (
    CrosspostSelection,
    PreparedImages,
    publish_note,
    save_unpublished_note,
)

# Create your views here.


def _save_and_maybe_crosspost(note, text, user, request, *, as_draft=False):
    """
    Shared helper to save a note and, when publishing, enqueue cross-posting.
    - note: Note instance (may be unsaved)
    - text: new text value
    - user: request.user or None
    - request: HttpRequest (for POST flags and FILES)
    - as_draft: True to keep as draft, False to publish
    """
    if as_draft:
        save_unpublished_note(
            note,
            text,
            uploaded_file=request.FILES.get("image"),
            image_alt=request.POST.get("image_alt") or "",
            remove_image=bool(request.POST.get("remove_image")),
        )
        return

    prepared_images = None
    files_to_delete = []
    uploaded_file = request.FILES.get("image")
    if uploaded_file and user and user.is_authenticated:
        from aether_notes.images import process_uploaded_image
        from django.core.files.base import ContentFile

        old_files = [
            (field.storage, field.name)
            for field in (note.image, note.image_hq)
            if field and field.name
        ]
        raw_bytes = uploaded_file.read()
        if raw_bytes:
            compressed, hq, bluesky = process_uploaded_image(raw_bytes)
            filename = uploaded_file.name or "image.jpg"
            if not filename.lower().endswith((".jpg", ".jpeg")):
                stem = filename.rsplit(".", 1)[0] if "." in filename else filename
                filename = f"{stem}.jpg"
            note.image.save(filename, ContentFile(compressed), save=False)
            note.image_alt = (request.POST.get("image_alt") or "").strip()[:1000]
            prepared_images = PreparedImages(
                hq=hq,
                bluesky=bluesky,
                compressed=compressed,
                alt=note.image_alt,
            )
            new_names = {note.image.name}
            files_to_delete = [
                (storage, name)
                for storage, name in old_files
                if name not in new_names
            ]
            note.image_hq = None
    elif request.POST.get("remove_image"):
        files_to_delete = [
            (field.storage, field.name)
            for field in (note.image, note.image_hq)
            if field and field.name
        ]
        note.image = None
        note.image_hq = None
        note.image_alt = ""

    note.text = text
    publish_note(
        note,
        user=user,
        selection=CrosspostSelection.from_post_data(request.POST),
        prepared_images=prepared_images,
        async_crossposts=True,
    )
    for storage, name in files_to_delete:
        if storage.exists(name):
            storage.delete(name)


@login_required
def drafts_list(request):
    """List drafts for the authenticated user."""
    drafts = Note.objects.filter(
        user=request.user,
        is_draft=True,
        queue_entry__isnull=True,
    ).order_by(
        "-last_modified"
    )
    return render(request, "aether_notes/drafts.html", {"drafts": drafts})


@login_required
def edit_draft(request, pk):
    """Edit or publish a draft."""
    try:
        draft = Note.objects.get(
            pk=pk,
            user=request.user,
            is_draft=True,
            queue_entry__isnull=True,
        )
    except Note.DoesNotExist:
        raise Http404("Draft not found")

    if request.method == "POST":
        text = (request.POST.get("text") or "").strip()
        if not text:
            return render(
                request,
                "aether_notes/edit_draft.html",
                {"draft": draft, "error": "Text cannot be empty."},
            )

        draft.text = text
        draft.last_modified = timezone.now()

        if "throw" in request.POST:
            _save_and_maybe_crosspost(
                draft, text, request.user, request, as_draft=False
            )
            return redirect("index")
        elif "add_queue" in request.POST:
            _enqueue_note(draft, text, request.user, request)
            messages.success(request, "Draft added to your queue.")
            return redirect("queue_list")
        else:
            save_unpublished_note(
                draft,
                text,
                uploaded_file=request.FILES.get("image"),
                image_alt=request.POST.get("image_alt") or draft.image_alt,
                remove_image=bool(request.POST.get("remove_image")),
            )
            return render(
                request, "aether_notes/edit_draft.html", {"draft": draft, "saved": True}
            )

    return render(request, "aether_notes/edit_draft.html", {"draft": draft})


def _queue_settings_for(user):
    settings, _ = PostQueueSettings.objects.get_or_create(user=user)
    return settings


def _lock_queue(user):
    PostQueueSettings.objects.filter(user=user).update(paused=F("paused"))
    return PostQueueSettings.objects.get(user=user)


def _enqueue_note(note, text, user, request):
    _queue_settings_for(user)
    with transaction.atomic():
        queue_settings = _lock_queue(user)
        queue_was_empty = not QueuedNote.objects.filter(user=user).exists()
        save_unpublished_note(
            note,
            text,
            uploaded_file=request.FILES.get("image"),
            image_alt=request.POST.get("image_alt") or note.image_alt or "",
            remove_image=bool(request.POST.get("remove_image")),
        )
        max_position = QueuedNote.objects.filter(user=user).aggregate(Max("position"))[
            "position__max"
        ]
        selection = CrosspostSelection.from_post_data(request.POST)
        QueuedNote.objects.create(
            note=note,
            user=user,
            position=(max_position or 0) + 1,
            crosspost_mastodon=selection.mastodon,
            crosspost_bluesky=selection.bluesky,
            crosspost_status_cafe=selection.status_cafe,
            crosspost_tumblr=selection.tumblr,
            crosspost_piclog_blue=selection.piclog_blue,
            status_cafe_face=selection.status_cafe_face or "",
        )
        if queue_was_empty and not queue_settings.paused:
            queue_settings.schedule_from()
            queue_settings.save(update_fields=["next_publish_at"])


def _compact_queue(user):
    entries = QueuedNote.objects.filter(user=user).order_by("position", "id")
    for position, entry in enumerate(entries, start=1):
        if entry.position != position:
            QueuedNote.objects.filter(pk=entry.pk).update(position=position)


def _repair_queue_after_deletion(user):
    _compact_queue(user)
    if not QueuedNote.objects.filter(user=user).exists():
        PostQueueSettings.objects.filter(user=user).update(next_publish_at=None)


@login_required
def queue_list(request):
    queue_settings = _queue_settings_for(request.user)
    entries = QueuedNote.objects.filter(user=request.user).select_related("note")
    return render(
        request,
        "aether_notes/queue.html",
        {"queue_entries": entries, "queue_settings": queue_settings},
    )


@login_required
def edit_queue_item(request, pk):
    _queue_settings_for(request.user)
    if request.method == "POST":
        with transaction.atomic():
            _lock_queue(request.user)
            try:
                entry = QueuedNote.objects.select_related("note").get(
                    pk=pk,
                    user=request.user,
                )
            except QueuedNote.DoesNotExist:
                raise Http404("Queued note not found")

            text = (request.POST.get("text") or "").strip()
            if not text:
                return render(
                    request,
                    "aether_notes/edit_queue_item.html",
                    {"queue_entry": entry, "error": "Text cannot be empty."},
                )
            save_unpublished_note(
                entry.note,
                text,
                uploaded_file=request.FILES.get("image"),
                image_alt=request.POST.get("image_alt") or entry.note.image_alt,
                remove_image=bool(request.POST.get("remove_image")),
            )
            selection = CrosspostSelection.from_post_data(request.POST)
            entry.crosspost_mastodon = selection.mastodon
            entry.crosspost_bluesky = selection.bluesky
            entry.crosspost_status_cafe = selection.status_cafe
            entry.crosspost_tumblr = selection.tumblr
            entry.crosspost_piclog_blue = selection.piclog_blue
            entry.status_cafe_face = selection.status_cafe_face or ""
            entry.save()
        messages.success(request, "Queued note updated.")
        return redirect("queue_list")

    try:
        entry = QueuedNote.objects.select_related("note").get(
            pk=pk,
            user=request.user,
        )
    except QueuedNote.DoesNotExist:
        raise Http404("Queued note not found")

    return render(
        request,
        "aether_notes/edit_queue_item.html",
        {"queue_entry": entry},
    )


@login_required
@require_POST
def update_queue_settings(request):
    try:
        interval_value = int(request.POST.get("interval_value", ""))
    except (TypeError, ValueError):
        interval_value = 0
    interval_unit = request.POST.get("interval_unit")
    if not 1 <= interval_value <= 365 or interval_unit not in {
        PostQueueSettings.UNIT_HOURS,
        PostQueueSettings.UNIT_DAYS,
    }:
        messages.error(request, "Choose an interval from 1 to 365 hours or days.")
        return redirect("queue_list")

    _queue_settings_for(request.user)
    with transaction.atomic():
        queue_settings = _lock_queue(request.user)
        queue_settings.interval_value = interval_value
        queue_settings.interval_unit = interval_unit
        if not queue_settings.paused and QueuedNote.objects.filter(user=request.user).exists():
            queue_settings.schedule_from()
        else:
            queue_settings.next_publish_at = None
        queue_settings.save()
    messages.success(request, "Queue interval updated.")
    return redirect("queue_list")


@login_required
@require_POST
def toggle_queue(request):
    _queue_settings_for(request.user)
    with transaction.atomic():
        queue_settings = _lock_queue(request.user)
        queue_settings.paused = not queue_settings.paused
        if queue_settings.paused:
            queue_settings.next_publish_at = None
        elif QueuedNote.objects.filter(user=request.user).exists():
            queue_settings.schedule_from()
        queue_settings.save()
    messages.success(
        request,
        "Queue paused." if queue_settings.paused else "Queue resumed.",
    )
    return redirect("queue_list")


@login_required
@require_POST
def move_queue_item(request, pk, direction):
    if direction not in {"up", "down"}:
        raise Http404("Invalid queue direction")
    _queue_settings_for(request.user)
    with transaction.atomic():
        _lock_queue(request.user)
        try:
            entry = QueuedNote.objects.get(pk=pk, user=request.user)
        except QueuedNote.DoesNotExist:
            raise Http404("Queued note not found")
        target_position = entry.position + (-1 if direction == "up" else 1)
        neighbor = QueuedNote.objects.filter(
            user=request.user,
            position=target_position,
        ).first()
        if neighbor:
            temporary = (
                QueuedNote.objects.filter(user=request.user).aggregate(Max("position"))[
                    "position__max"
                ]
                + 1
            )
            QueuedNote.objects.filter(pk=entry.pk).update(position=temporary)
            QueuedNote.objects.filter(pk=neighbor.pk).update(position=entry.position)
            QueuedNote.objects.filter(pk=entry.pk).update(position=target_position)
    return redirect("queue_list")


@login_required
@require_POST
def delete_queue_item(request, pk):
    _queue_settings_for(request.user)
    with transaction.atomic():
        _lock_queue(request.user)
        try:
            entry = QueuedNote.objects.select_related("note").get(
                pk=pk,
                user=request.user,
            )
        except QueuedNote.DoesNotExist:
            raise Http404("Queued note not found")
        entry.note.delete()
        _repair_queue_after_deletion(request.user)
    messages.success(request, "Queued note deleted.")
    return redirect("queue_list")


def index(request):
    now = timezone.now()
    cutoff = now - datetime.timedelta(days=7)
    qs = (
        Note.objects.filter(pub_date__gte=cutoff, is_draft=False)
        .order_by("-pub_date")
        .prefetch_related("crossposts")
    )
    notes = list(qs[:200])

    # Attach display metadata for fading and expiry labels
    max_age = 7 * 24 * 3600
    for n in notes:
        age = (now - n.pub_date).total_seconds()
        ratio = min(max(age / max_age, 0.0), 1.0)
        # Map to opacity: newer -> 1.0, oldest (7 days) -> 0.4
        n.opacity = round(1.0 - 0.6 * ratio, 3)
        remaining = max(0, int(max_age - age))
        days = remaining // 86400
        hours = (remaining % 86400) // 3600
        minutes = (remaining % 3600) // 60
        if days > 0:
            n.expires_in = f"{days}d {hours}h"
        else:
            n.expires_in = f"{hours}h {minutes}m"

    context = {
        "latest_note_list": notes,
        "now_ts": int(now.timestamp()),
        "cutoff_ts": int(cutoff.timestamp()),
    }
    return render(request, "aether_notes/index.html", context)


@rate_limited("create_note", limit=2, window_seconds=60)
def create_note(request):
    if request.method != "POST":
        return redirect(reverse("index"))

    text = (request.POST.get("text") or "").strip()
    if not text:
        return redirect(reverse("index"))

    created_device_id = (request.POST.get("device_id") or "").strip() or None

    # Check if saving as draft
    save_as_draft = "save_draft" in request.POST
    add_to_queue = "add_queue" in request.POST

    if request.user.is_authenticated:
        # Authenticated: ignore provided author, bind to user
        author = request.user.username
        user = request.user
    else:
        raw_author = (request.POST.get("author") or "").strip()
        author = raw_author or "anonymous"
        user = None
        # Reject reserved usernames (registered accounts)
        if raw_author:
            User = get_user_model()
            if User.objects.filter(username__iexact=raw_author).exists():
                messages.error(request, "Reserved username. Sign in to use it.")
                return redirect(reverse("index"))

    if len(author) > Note._meta.get_field("author").max_length:
        return JsonResponse({"ok": False, "error": "author_too_long"}, status=400)

    if add_to_queue:
        if not request.user.is_authenticated:
            messages.error(request, "Sign in to add notes to your queue.")
            return redirect(reverse("index"))
        new_note = Note(
            text=text,
            author=author,
            user=user,
            pub_date=timezone.now(),
            created_device_id=created_device_id,
        )
        _enqueue_note(new_note, text, user, request)
        messages.success(request, "Note added to your queue.")
        return redirect("queue_list")

    if save_as_draft and request.user.is_authenticated:
        new_note = Note(
            text=text,
            author=author,
            user=user,
            pub_date=timezone.now(),
            created_device_id=created_device_id,
        )
        _save_and_maybe_crosspost(new_note, text, user, request, as_draft=True)
        return redirect("drafts_list")

    new_note = Note(
        text=text,
        author=author,
        user=user,
        pub_date=timezone.now(),
        created_device_id=created_device_id,
    )
    _save_and_maybe_crosspost(new_note, text, user, request, as_draft=False)
    return redirect(reverse("index"))


def about(request):
    return render(request, "aether_notes/about.html")


@csrf_exempt
@require_POST
def witness(request):
    """Record first-time views from a device for one or more notes.

    Accepts either:
    - Single note: { note_id: int, device_id: string }
    - Batch: { note_ids: [int, ...], device_id: string }
    
    Returns:
    - Single: { ok: bool, views: int, already?: bool }
    - Batch: { ok: bool, results: { note_id: { views: int, already?: bool }, ... } }
    """
    device_id = (request.POST.get("device_id") or "").strip()
    if not device_id:
        return JsonResponse({"ok": False, "error": "missing_device_id"}, status=400)

    # Check if batch request (note_ids) or single (note_id)
    note_ids_raw = request.POST.get("note_ids")
    
    if note_ids_raw:
        # Batch processing
        try:
            # Parse comma-separated note IDs
            note_ids = [int(nid.strip()) for nid in note_ids_raw.split(",") if nid.strip()]
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "invalid_note_ids"}, status=400)
        
        if not note_ids:
            return JsonResponse({"ok": False, "error": "empty_note_ids"}, status=400)
        
        # Fetch all valid notes
        notes = {n.id: n for n in Note.objects.filter(id__in=note_ids)}
        results = {}
        
        with transaction.atomic():
            # Prepare batch inserts
            to_create = []
            note_ids_to_increment = []
            
            for note_id in note_ids:
                if note_id not in notes:
                    results[note_id] = {"error": "not_found"}
                    continue
                
                # Check if already witnessed
                if NoteView.objects.filter(note_id=note_id, device_id=device_id).exists():
                    results[note_id] = {"views": notes[note_id].views, "already": True}
                else:
                    to_create.append(NoteView(note_id=note_id, device_id=device_id))
                    note_ids_to_increment.append(note_id)
            
            # Bulk create new witness records
            if to_create:
                NoteView.objects.bulk_create(to_create, ignore_conflicts=True)
                # Increment view counts
                Note.objects.filter(id__in=note_ids_to_increment).update(views=F("views") + 1)
            
            # Fetch updated counts for newly witnessed notes
            for note_id in note_ids_to_increment:
                notes[note_id].refresh_from_db(fields=["views"])
                results[note_id] = {"views": notes[note_id].views}
        
        return JsonResponse({"ok": True, "results": results})
    
    else:
        # Single note processing (backward compatibility)
        try:
            note_id = int(request.POST.get("note_id"))
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)

        if not note_id:
            return JsonResponse({"ok": False, "error": "missing_fields"}, status=400)

        try:
            note = Note.objects.get(pk=note_id)
        except Note.DoesNotExist:
            return JsonResponse({"ok": False, "error": "not_found"}, status=404)

        try:
            with transaction.atomic():
                NoteView.objects.create(note=note, device_id=device_id)
                Note.objects.filter(pk=note.pk).update(views=F("views") + 1)
        except IntegrityError:
            # Already witnessed; ignore
            return JsonResponse(
                {"ok": True, "already": True, "views": note.views}, status=200
            )

        # Fetch updated count
        note.refresh_from_db(fields=["views"])
        return JsonResponse({"ok": True, "views": note.views})


@csrf_exempt
@require_POST
def delete_note(request):
    """Delete a note if and only if the caller's device_id matches creator.

    Expects form or x-www-form-urlencoded with: note_id, device_id
    Returns JSON { ok: bool } with 200 on success, 403 on forbidden, 404 if missing.
    """
    try:
        note_id = int(request.POST.get("note_id"))
        device_id = (request.POST.get("device_id") or "").strip()
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)

    if not note_id or not device_id:
        return JsonResponse({"ok": False, "error": "missing_fields"}, status=400)

    try:
        note = Note.objects.get(pk=note_id)
    except Note.DoesNotExist:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    # if the note belongs to a user then only that user can delete it
    if note.user is not None:
        if not request.user.is_authenticated or request.user != note.user:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "forbidden",
                    "message": f"You don't own this note so can't delete it. Only '{note.user.username}' can.",
                },
                status=403,
            )

    else:
        # if the note is anonymous, only the device that created it can delete it
        if not note.created_device_id or note.created_device_id != device_id:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "forbidden",
                    "message": "Only the device that created this note can delete it.",
                },
                status=403,
            )

    queued_user = (
        note.user if QueuedNote.objects.filter(note_id=note.pk).exists() else None
    )
    with transaction.atomic():
        if queued_user is not None:
            _lock_queue(queued_user)
        note.delete()
        if queued_user is not None:
            _repair_queue_after_deletion(queued_user)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def flag_note(request):
    """Toggle a flag for a note per device (flag/unflag). Expects: note_id, device_id."""
    try:
        note_id = int(request.POST.get("note_id"))
        device_id = (request.POST.get("device_id") or "").strip()
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)

    if not note_id or not device_id:
        return JsonResponse({"ok": False, "error": "missing_fields"}, status=400)

    try:
        note = Note.objects.get(pk=note_id)
    except Note.DoesNotExist:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    # Try to create a flag; if it already exists, unflag instead.
    try:
        with transaction.atomic():
            NoteFlag.objects.create(note=note, device_id=device_id)
            Note.objects.filter(pk=note.pk).update(flags=F("flags") + 1)
            note.refresh_from_db(fields=["flags"])
            return JsonResponse({"ok": True, "flags": note.flags, "flagged": True})
    except IntegrityError:
        # Already flagged by this device — unflag (delete) and decrement count if possible.
        with transaction.atomic():
            NoteFlag.objects.filter(note=note, device_id=device_id).delete()
            # Prevent negative values.
            Note.objects.filter(pk=note.pk, flags__gt=0).update(flags=F("flags") - 1)
            note.refresh_from_db(fields=["flags"])
            return JsonResponse({"ok": True, "flags": note.flags, "flagged": False})
