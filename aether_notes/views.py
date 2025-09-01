import datetime
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db import IntegrityError, transaction
from django.db.models import F
from .models import Note, NoteView


# Create your views here.
def index(request):
    now = timezone.now()
    cutoff = now - datetime.timedelta(days=2)
    qs = Note.objects.filter(pub_date__gte=cutoff).order_by("-pub_date")
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


def create_note(request):
    if request.method == "POST":
        text = (request.POST.get("text") or "").strip()
        if not text:
            return redirect(reverse("index"))

        author = (request.POST.get("author") or "").strip() or "anonymous"
        # Soft cap to 2000 chars
        if len(text) > 2000:
            text = text[:2000]

        new_note = Note(
            text=text,
            author=author,
            pub_date=timezone.now(),
        )
        new_note.save()

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
        return JsonResponse({"ok": True, "already": True, "views": note.views}, status=200)

    # Fetch updated count
    note.refresh_from_db(fields=["views"])
    return JsonResponse({"ok": True, "views": note.views})
