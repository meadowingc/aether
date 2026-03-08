import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.social import post_selected_networks_async
from accounts.utils import rate_limited

from .models import Note, NoteFlag, NoteView

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
    note.text = text
    if as_draft:
        note.is_draft = True
    else:
        note.is_draft = False
        note.pub_date = timezone.now()

    # Handle image upload (authenticated users only)
    image_hq_bytes = None
    image_bluesky_bytes = None
    image_compressed_bytes = None
    image_alt = ""

    uploaded_file = request.FILES.get("image") if request.FILES else None
    if uploaded_file and user and user.is_authenticated:
        from aether_notes.images import process_uploaded_image, convert_for_bluesky
        from django.core.files.base import ContentFile

        raw_bytes = uploaded_file.read()
        if raw_bytes:
            compressed, hq, bsky = process_uploaded_image(raw_bytes)
            image_hq_bytes = hq
            image_bluesky_bytes = bsky
            image_compressed_bytes = compressed

            # Save the compressed version for display
            filename = uploaded_file.name or "image.jpg"
            if not filename.lower().endswith((".jpg", ".jpeg")):
                filename = filename.rsplit(".", 1)[0] + ".jpg" if "." in filename else filename + ".jpg"
            note.image.save(filename, ContentFile(compressed), save=False)
            # Save the HQ version for crossposting later (e.g. drafts)
            note.image_hq.save("hq_" + filename, ContentFile(hq), save=False)
            note.image_alt = (request.POST.get("image_alt") or "").strip()[:1000]
            image_alt = note.image_alt

    # When publishing a draft that already has an image but no new upload,
    # read the stored HQ image to produce crosspost versions.
    if not uploaded_file and not as_draft and note.image and note.image_hq:
        from aether_notes.images import convert_for_bluesky, compress_for_storage
        try:
            note.image_hq.open("rb")
            hq_bytes = note.image_hq.read()
            note.image_hq.close()
            if hq_bytes:
                image_hq_bytes = hq_bytes
                image_bluesky_bytes = convert_for_bluesky(hq_bytes)
                image_compressed_bytes = compress_for_storage(hq_bytes)
                image_alt = note.image_alt or ""
        except Exception:
            pass

    # Delete the HQ file once we've extracted what we need for crossposting.
    if not as_draft and note.image_hq:
        try:
            note.image_hq.delete(save=False)
        except Exception:
            pass
        note.image_hq = None

    note.save()

    # When publishing, mirror create_note's crosspost behavior
    if not as_draft and user and hasattr(user, "profile"):
        prof = user.profile
        want_masto = bool(request.POST.get("xp_mastodon"))
        want_bsky = bool(request.POST.get("xp_bluesky"))
        want_status_cafe = bool(request.POST.get("xp_status_cafe"))
        want_tumblr = bool(request.POST.get("xp_tumblr"))
        want_piclog_blue = bool(request.POST.get("xp_piclog_blue"))
        status_cafe_face = (
            request.POST.get("xp_status_cafe_face") or ""
        ).strip() or None

        if any([want_masto, want_bsky, want_status_cafe, want_tumblr, want_piclog_blue]):
            try:
                post_selected_networks_async(
                    prof,
                    note.text,
                    want_masto=want_masto,
                    want_bluesky=want_bsky,
                    want_status_cafe=want_status_cafe,
                    want_tumblr=want_tumblr,
                    want_piclog_blue=want_piclog_blue,
                    status_cafe_face=status_cafe_face,
                    note=note,
                    image_hq_bytes=image_hq_bytes,
                    image_bluesky_bytes=image_bluesky_bytes,
                    image_compressed_bytes=image_compressed_bytes,
                    image_alt=image_alt,
                )
            except Exception:
                # Defensive: don't let crosspost failures block the request
                pass


@login_required
def drafts_list(request):
    """List drafts for the authenticated user."""
    drafts = Note.objects.filter(user=request.user, is_draft=True).order_by(
        "-last_modified"
    )
    return render(request, "aether_notes/drafts.html", {"drafts": drafts})


@login_required
def edit_draft(request, pk):
    """Edit or publish a draft."""
    try:
        draft = Note.objects.get(pk=pk, user=request.user, is_draft=True)
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
        else:
            draft.save()
            return render(
                request, "aether_notes/edit_draft.html", {"draft": draft, "saved": True}
            )

    return render(request, "aether_notes/edit_draft.html", {"draft": draft})


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
    print("DEBUG: create_note view called, method =", request.method)
    if request.method != "POST":
        return redirect(reverse("index"))

    text = (request.POST.get("text") or "").strip()
    if not text:
        return redirect(reverse("index"))

    created_device_id = (request.POST.get("device_id") or "").strip() or None

    # Check if saving as draft
    save_as_draft = "save_draft" in request.POST

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

    # validate
    if len(author) > Note._meta.get_field("author").max_length:
        return JsonResponse({"ok": False, "error": "author_too_long"}, status=400)

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

    note.delete()
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
