from __future__ import annotations
from typing import Any
import json

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import (
    HttpRequest,
    HttpResponse,
    JsonResponse,
    HttpResponseBadRequest,
)
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import RegistrationForm, ProfileForm
from .models import Profile
from .utils import rate_limited, client_ip
from aether_notes.models import Note
from django.utils.safestring import mark_safe

User = get_user_model()

@rate_limited("register", limit=5, window_seconds=60)
def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("index")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("index")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})

@login_required
def settings_view(request: HttpRequest) -> HttpResponse:
    profile: Profile = request.user.profile  # type: ignore[attr-defined]
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            # If user clicked a clear error button
            if "clear_error" in request.POST:
                profile.clear_crosspost_error()
            return redirect(reverse("accounts:settings"))
    else:
        form = ProfileForm(instance=profile)
    # Show existing secrets (user can clear by submitting blank). Consider masking in future if needed.
    ctx = {
        "form": form,
        "profile": profile,
    }
    return render(request, "accounts/settings.html", ctx)

def check_username(request: HttpRequest) -> HttpResponse:
    username = (request.GET.get("u") or "").strip()
    available = False
    if username:
        available = not User.objects.filter(username__iexact=username).exists()
    return JsonResponse({"available": available})

@login_required
def clear_crosspost_error(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    request.user.profile.clear_crosspost_error()  # type: ignore[attr-defined]
    return JsonResponse({"ok": True})

@login_required
def test_mastodon(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    profile: Profile = request.user.profile  # type: ignore[attr-defined]
    inst = (profile.mastodon_instance or "").rstrip("/")
    token = profile.mastodon_token or ""
    if not inst or not token:
        return JsonResponse({"ok": False, "error": "missing_credentials"})
    import httpx
    try:
        r = httpx.get(f"{inst}/api/v1/accounts/verify_credentials", headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if r.status_code == 200:
            profile.clear_crosspost_error()
            return JsonResponse({"ok": True})
        profile.record_crosspost_error(f"Mastodon test failed: {r.status_code}")
        return JsonResponse({"ok": False, "error": f"status_{r.status_code}"})
    except Exception as e:  # noqa: BLE001
        profile.record_crosspost_error(f"Mastodon exception: {e.__class__.__name__}")
        return JsonResponse({"ok": False, "error": "exception"})

@login_required
def test_bluesky(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    profile: Profile = request.user.profile  # type: ignore[attr-defined]
    handle = profile.bluesky_handle or ""
    app_pw = profile.bluesky_app_password or ""
    if not handle or not app_pw:
        return JsonResponse({"ok": False, "error": "missing_credentials"})
    try:
        from atproto import Client
        client = Client()
        client.login(handle, app_pw)
        profile.clear_crosspost_error()
        return JsonResponse({"ok": True})
    except Exception as e:  # noqa: BLE001
        profile.record_crosspost_error(f"Bluesky exception: {e.__class__.__name__}")
        return JsonResponse({"ok": False, "error": "exception"})

# Helper to detect JSON/intended AJAX
def wants_json(request: HttpRequest) -> bool:
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return True
    accept = request.headers.get("accept", "")
    return "application/json" in accept

def rate_status(request: HttpRequest) -> HttpResponse:
    # Optional endpoint to introspect IP for debugging (not linked)
    if request.method != "GET":
        return HttpResponseBadRequest("GET only")
    ip = client_ip(request)
    return JsonResponse({"ip": ip})

@login_required
def mastodon_oauth_start(request: HttpRequest) -> HttpResponse:
    """
    Dynamic Mastodon (ActivityPub-compatible) OAuth app registration + auth redirect.
    Uses profile.mastodon_instance (must be set). Stores client creds in session for callback.
    """
    profile: Profile = request.user.profile  # type: ignore[attr-defined]
    instance = (profile.mastodon_instance or "").rstrip("/")
    if not instance:
        return HttpResponseBadRequest("Set Mastodon instance first and save settings.")

    import httpx
    from urllib.parse import urlencode

    # If already have a token, allow re-auth to refresh scope.
    redirect_uri = request.build_absolute_uri(reverse("accounts:mastodon_oauth_callback"))
    session_key = "mastodon_oauth"
    data = request.session.get(session_key)

    if not data or data.get("instance") != instance:
        # Register app (scopes: write read)
        try:
            r = httpx.post(
                f"{instance}/api/v1/apps",
                data={
                    "client_name": "Aether Crossposter",
                    "redirect_uris": redirect_uri,
                    "scopes": "read write",
                    "website": "https://aether.meadow.cafe",
                },
                timeout=10,
            )
            if r.status_code not in (200, 202):
                return HttpResponse(f"App registration failed ({r.status_code})", status=500)
            payload = r.json()
            client_id = payload.get("client_id")
            client_secret = payload.get("client_secret")
            if not client_id or not client_secret:
                return HttpResponse("Invalid app registration response", status=500)
            request.session[session_key] = {
                "instance": instance,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            }
            request.session.modified = True
            data = request.session[session_key]
        except Exception as e:  # noqa: BLE001
            return HttpResponse(f"Registration exception: {e.__class__.__name__}", status=500)

    auth_url = (
        f"{instance}/oauth/authorize?"
        + urlencode(
            {
                "client_id": data["client_id"],
                "redirect_uri": data["redirect_uri"],
                "response_type": "code",
                "scope": "read write",
            }
        )
    )
    return redirect(auth_url)

@login_required
def mastodon_oauth_callback(request: HttpRequest) -> HttpResponse:
    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing code")
    session_key = "mastodon_oauth"
    data = request.session.get(session_key)
    if not data:
        return HttpResponseBadRequest("Session expired; restart OAuth.")

    import httpx

    try:
        r = httpx.post(
            f"{data['instance']}/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": data["client_id"],
                "client_secret": data["client_secret"],
                "redirect_uri": data["redirect_uri"],
                "scope": "read write",
            },
            timeout=10,
        )
        if r.status_code != 200:
            return HttpResponse(f"Token exchange failed ({r.status_code})", status=500)
        payload = r.json()
        access_token = payload.get("access_token")
        if not access_token:
            return HttpResponse("No access_token in response", status=500)
        profile: Profile = request.user.profile  # type: ignore[attr-defined]
        profile.mastodon_token = access_token
        profile.crosspost_mastodon = True
        profile.save(update_fields=["mastodon_token", "crosspost_mastodon"])
    except Exception as e:  # noqa: BLE001
        return HttpResponse(f"OAuth exception: {e.__class__.__name__}", status=500)

    # Cleanup session (optional)
    try:
        del request.session[session_key]
    except KeyError:
        pass
    return redirect(reverse("accounts:settings"))

def logout_view(request: HttpRequest) -> HttpResponse:
    """
    Simple logout accepting GET (for header link) or POST, then redirect home.
    """
    logout(request)
    return redirect("index")

def user_archive(request: HttpRequest, username: str) -> HttpResponse:
    """Public archive/profile page for a user if they opted in.

    Shows all their notes (no 48h cutoff) newest first.
    404 if user not found or archive disabled.
    """
    try:
        user = User.objects.get(username__iexact=username)
    except User.DoesNotExist:
        return render(request, "404.html", status=404)  # fallback; custom template optional
    if not hasattr(user, "profile") or not user.profile.show_archive:  # type: ignore[attr-defined]
        return render(request, "404.html", status=404)

    # Fetch latest 200 notes authored by this user (persist even if beyond feed window)
    notes = Note.objects.filter(user=user).order_by("-pub_date")[:200]
    profile: Profile = user.profile  # type: ignore[attr-defined]

    # Markdown rendering (safe subset) for bio
    rendered_bio = ""
    if profile.bio:
        bio_source = profile.bio
        try:
            from markdown_it import MarkdownIt  # type: ignore
            md = MarkdownIt(
                "commonmark",
                {
                    "html": False,       # disallow raw HTML
                    "linkify": True,     # auto link plain URLs
                    "typographer": True,
                },
            )
            # Use default enabled rules; that's enough for emphasis / code / lists / blockquotes
            raw_html = md.render(bio_source)
            rendered_bio = mark_safe(raw_html)
        except Exception:
            # Fallback: extremely small inline markdown ( *em* _em_ `code` ) without raw HTML
            import html, re
            esc = html.escape(bio_source)
            # code spans first
            esc = re.sub(r"`([^`]{1,200})`", lambda m: f"<code>{m.group(1)}</code>", esc)
            # bold (**) then emphasis (*) and _ _
            esc = re.sub(r"\*\*([^*]{1,400})\*\*", r"<strong>\1</strong>", esc)
            esc = re.sub(r"\*([^*]{1,400})\*", r"<em>\1</em>", esc)
            esc = re.sub(r"__([^_]{1,400})__", r"<strong>\1</strong>", esc)
            esc = re.sub(r"_([^_]{1,400})_", r"<em>\1</em>", esc)
            # simple line breaks
            esc = esc.replace("\r\n", "\n").replace("\r", "\n")
            rendered_bio = mark_safe("<p>" + esc.replace("\n\n", "</p><p>").replace("\n", "<br>") + "</p>")

    ctx = {"archive_user": user, "profile": profile, "notes": notes, "rendered_bio": rendered_bio}
    return render(request, "accounts/archive.html", ctx)
