import datetime

from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.contrib.auth import get_user_model
from django.contrib import messages
from accounts.utils import rate_limited
from accounts.social import post_selected_networks_async

from .models import Note, NoteFlag, NoteView
from django.contrib.auth.decorators import login_required
from django.http import Http404


# Create your views here.

@login_required
def drafts_list(request):
    """List drafts for the authenticated user."""
    drafts = Note.objects.filter(user=request.user, is_draft=True).order_by("-last_modified")
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
            return render(request, "aether_notes/edit_draft.html", {"draft": draft, "error": "Text cannot be empty."})

        draft.text = text
        draft.last_modified = timezone.now()

        if "throw" in request.POST:
            draft.is_draft = False
            draft.pub_date = timezone.now()
            draft.save()
            return redirect("index")
        else:
            draft.save()
            return render(request, "aether_notes/edit_draft.html", {"draft": draft, "saved": True})

    return render(request, "aether_notes/edit_draft.html", {"draft": draft})

def index(request):
    now = timezone.now()
    cutoff = now - datetime.timedelta(days=2)
    qs = Note.objects.filter(pub_date__gte=cutoff).order_by("-pub_date").prefetch_related("crossposts")
    notes = list(qs[:200])

    # Attach display metadata for fading and expiry labels
    max_age = 2 * 24 * 3600
    for n in notes:
        age = (now - n.pub_date).total_seconds()
        ratio = min(max(age / max_age, 0.0), 1.0)
        # Map to opacity: newer -> 1.0, oldest (48h) -> 0.4
        n.opacity = round(1.0 - 0.6 * ratio, 3)
        remaining = max(0, int(max_age - age))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
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

    if len(text) > 200:
        return JsonResponse({"ok": False, "error": "text_too_long"}, status=400)

    if save_as_draft and request.user.is_authenticated:
        new_note = Note(
            text=text,
            author=author,
            user=user,
            pub_date=timezone.now(),
            created_device_id=created_device_id,
            is_draft=True,
        )
        new_note.save()
        return redirect("drafts_list")

    new_note = Note(
        text=text,
        author=author,
        user=user,
        pub_date=timezone.now(),
        created_device_id=created_device_id,
    )
    new_note.save()

    # Cross-post asynchronously (fire-and-forget)
    if request.user.is_authenticated and user and hasattr(user, "profile"):
        prof = user.profile
        want_masto = bool(request.POST.get("xp_mastodon"))
        want_bsky = bool(request.POST.get("xp_bluesky"))
        want_status_cafe = bool(request.POST.get("xp_status_cafe"))
        status_cafe_face = (request.POST.get("xp_status_cafe_face") or "").strip() or None

        if any([want_masto, want_bsky, want_status_cafe]):
            try:
                post_selected_networks_async(
                    prof,
                    new_note.text,
                    want_masto=want_masto,
                    want_bluesky=want_bsky,
                    want_status_cafe=want_status_cafe,
                    status_cafe_face=status_cafe_face,
                    note=new_note,
                )
            except Exception:  # pragma: no cover - defensive
                pass

    return redirect(reverse("index"))


def about(request):
    return render(request, "aether_notes/about.html")


@require_POST
def witness(request):
    """Record a first-time view from a device for a given note.

    Expects JSON: { note_id: int, device_id: string }
    """
    try:
        note_id = int(request.POST.get("note_id"))
        device_id = (request.POST.get("device_id") or "").strip()
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid_payload"}, status=400)

    if not device_id or not note_id:
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
