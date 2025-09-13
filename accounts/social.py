from __future__ import annotations
import threading
from typing import Tuple

from .models import Profile

MASTODON_FALLBACK_LIMIT = 2000  # default; overridden per-user via Profile.mastodon_char_limit
BLUESKY_LIMIT = 300

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
