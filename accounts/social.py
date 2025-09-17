from __future__ import annotations
import threading
from typing import Tuple

from .models import Profile

MASTODON_FALLBACK_LIMIT = 2000  # default; overridden per-user via Profile.mastodon_char_limit
BLUESKY_LIMIT = 300
STATUS_CAFE_LIMIT = 140

def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1].rstrip() + "…"

def post_mastodon(profile: Profile, text: str) -> Tuple[bool, str | None]:
    inst = (profile.mastodon_instance or "").rstrip("/")
    token = profile.mastodon_token or ""
    if not inst or not token or not profile.crosspost_mastodon:
        return False, "disabled_or_missing"
    try:
        from mastodon import Mastodon  # type: ignore
        api = Mastodon(api_base_url=inst, access_token=token)
        limit = int(getattr(profile, "mastodon_char_limit", MASTODON_FALLBACK_LIMIT) or MASTODON_FALLBACK_LIMIT)
        status = api.status_post(_truncate(text, limit))
        return True, str(status.get("id")) if isinstance(status, dict) else None
    except Exception as e:  # noqa: BLE001
        profile.record_crosspost_error(f"Mastodon post failed: {e.__class__.__name__}")
        return False, None

def post_bluesky(profile: Profile, text: str) -> Tuple[bool, str | None]:
    handle = profile.bluesky_handle or ""
    app_pw = profile.bluesky_app_password or ""
    if not handle or not app_pw or not profile.crosspost_bluesky:
        return False, "disabled_or_missing"
    try:
        from atproto import Client  # type: ignore
        client = Client()
        client.login(handle, app_pw)
        post = client.send_post(text=_truncate(text, BLUESKY_LIMIT))
        return True, getattr(post, "uri", None)
    except Exception as e:  # noqa: BLE001
        profile.record_crosspost_error(f"Bluesky post failed: {e.__class__.__name__}")
        return False, None


def post_status_cafe(profile: Profile, text: str) -> Tuple[bool, str | None]:
    """Programmatic login + status submit to status.cafe.

    Since there is no public API we mimic browser form posts:
      1. GET /login -> parse CSRF token (gorilla.csrf.Token)
      2. POST /check-login with name+password+token (follow redirects)
      3. GET / (home) to obtain posting form CSRF token
      4. POST /add with face (emoji) + content + gorilla.csrf.Token

    Returns (ok, None). On failure, records a concise error code.
    """
    username = profile.status_cafe_username or ""
    password = profile.status_cafe_password or ""
    if not username or not password or not profile.crosspost_status_cafe:
        return False, "disabled_or_missing"

    try:
        import httpx
        from bs4 import BeautifulSoup  # type: ignore

        # Shared client with cookie persistence
        headers = {"User-Agent": "AetherCrossposter/0.1 (+https://aether.meadow.cafe)"}
        with httpx.Client(base_url="https://status.cafe", headers=headers, timeout=15, follow_redirects=True) as client:
            # Step 1: fetch login page
            r = client.get("/login")
            if r.status_code != 200:
                profile.record_crosspost_error(f"Status.cafe login_get {r.status_code}")
                return False, None

            soup = BeautifulSoup(r.text, "html.parser")
            token_input = soup.find("input", {"name": "gorilla.csrf.Token"})
            if not token_input or not token_input.get("value"):
                profile.record_crosspost_error("Status.cafe token_missing")
                return False, None

            csrf_login = token_input["value"]

            # Step 2: post credentials
            client.post(
                "/check-login",
                data={
                    "gorilla.csrf.Token": csrf_login,
                    "name": username,
                    "password": password,
                },
            )

            # Verify authenticated session by requesting /settings (will redirect to /login if not signed in)
            rs = client.get("/settings")
            if "login" in rs.url.path.lower():
                profile.record_crosspost_error("Status.cafe auth_failed")
                return False, None

            # Step 3: fetch homepage for post form
            r3 = client.get("/")
            if r3.status_code != 200:
                profile.record_crosspost_error(f"Status.cafe home_get {r3.status_code}")
                return False, None

            soup_home = BeautifulSoup(r3.text, "html.parser")
            token_post_input = soup_home.find("form", {"action": "/add"})
            if not token_post_input:
                profile.record_crosspost_error("Status.cafe post_form_missing")
                return False, None

            hidden_csrf = token_post_input.find("input", {"name": "gorilla.csrf.Token"})
            if not hidden_csrf or not hidden_csrf.get("value"):
                profile.record_crosspost_error("Status.cafe post_token_missing")
                return False, None

            csrf_post = hidden_csrf["value"]

            face = profile.status_cafe_default_face or ""
            content = _truncate(text, STATUS_CAFE_LIMIT)
            r4 = client.post(
                "/add",
                data={
                    "gorilla.csrf.Token": csrf_post,
                    "face": face or "🙂",  # default emoji if unset
                    "content": content,
                },
            )

            if r4.status_code not in (200, 302):
                profile.record_crosspost_error(f"Status.cafe post_fail {r4.status_code}")
                return False, None

            # success (no ID to return)
            return True, None

    except Exception as e:  # noqa: BLE001
        profile.record_crosspost_error(f"Status.cafe exception: {e.__class__.__name__}")
        return False, None

def post_to_networks(profile: Profile, text: str) -> None:
    """
    Synchronous cross-post to selected networks.
    Errors recorded on profile; successes clear prior error.
    """
    any_error = False
    if profile.crosspost_mastodon:
        ok, _ = post_mastodon(profile, text)
        any_error = any_error or (not ok)
    if profile.crosspost_bluesky:
        ok, _ = post_bluesky(profile, text)
        any_error = any_error or (not ok)
    if getattr(profile, "crosspost_status_cafe", False):
        ok, _ = post_status_cafe(profile, text)
        any_error = any_error or (not ok)
    if not any_error and (profile.last_crosspost_error or profile.last_crosspost_error_at):
        profile.clear_crosspost_error()

def post_to_networks_async(profile: Profile, text: str) -> None:
    """
    Fire-and-forget threaded variant (example usage):
        from accounts.social import post_to_networks_async
        post_to_networks_async(request.user.profile, note.text)
    """
    t = threading.Thread(target=post_to_networks, args=(profile, text), daemon=True)
    t.start()
