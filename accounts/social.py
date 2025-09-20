from __future__ import annotations
import re
import threading
from typing import Tuple, Optional, List

from .models import Profile

MASTODON_FALLBACK_LIMIT = (
    2000  # default; overridden per-user via Profile.mastodon_char_limit
)
BLUESKY_LIMIT = 300

URL_RE = re.compile(r"https?://[\w\-._~%:/?#@!$&'()*+,;=]+", re.IGNORECASE)
STATUS_CAFE_LIMIT = 140


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1].rstrip() + "…"


def post_mastodon(profile: Profile, text: str) -> Tuple[bool, str | None, str | None]:
    inst = (profile.mastodon_instance or "").rstrip("/")
    token = profile.mastodon_token or ""
    if not inst or not token or not profile.crosspost_mastodon:
        return False, "disabled_or_missing", None
    try:
        from mastodon import Mastodon  # type: ignore

        api = Mastodon(api_base_url=inst, access_token=token)
        limit = int(
            getattr(profile, "mastodon_char_limit", MASTODON_FALLBACK_LIMIT)
            or MASTODON_FALLBACK_LIMIT
        )
        status = api.status_post(_truncate(text, limit))
        remote_id = None
        remote_url = None
        if isinstance(status, dict):
            if status.get("id") is not None:
                remote_id = str(status.get("id"))
            url_val = status.get("url")
            if isinstance(url_val, str):
                remote_url = url_val
            if not remote_url and remote_id:
                acct = status.get("account", {}) if isinstance(status.get("account"), dict) else {}
                username = acct.get("acct") if isinstance(acct, dict) else None
                if username:
                    remote_url = f"{inst}/@{username}/{remote_id}"
        return True, remote_id, remote_url
    except Exception as e:  # noqa: BLE001
        profile.record_crosspost_error(f"Mastodon post failed: {e.__class__.__name__}")
        return False, None, None


def _build_bluesky_facets_with_richtext(text: str):  # pragma: no cover (depends on atproto internals)
    """Attempt to use atproto.RichText to auto-detect facets.

    Returns (processed_text, facets) or (text, None) on failure.
    """
    try:  # type: ignore
        from atproto import RichText  # type: ignore

        rt = RichText(text)
        rt.detect_facets()
        return rt.text, rt.facets or None
    except Exception:  # noqa: BLE001
        return text, None


def _build_bluesky_facets_manual(text: str):
    """Manual (minimal) facet construction for links if RichText helper unavailable.

    Bluesky's spec requires UTF-16 code unit offsets. Python's internal indexing is
    code point based, so we convert slices to UTF-16 lengths via encode('utf-16-le').
    This is a simplified approach and may miss certain edge cases, but is acceptable
    as a fallback.
    """
    facets: List[dict] = []
    for m in URL_RE.finditer(text):
        url = m.group(0)
        start_cp = m.start()
        end_cp = m.end()
        # Compute UTF-16 code unit offsets (excluding BOM) by encoding substrings
        prefix_utf16_len = len(text[:start_cp].encode("utf-16-le")) // 2
        match_utf16_len = len(text[start_cp:end_cp].encode("utf-16-le")) // 2
        facets.append(
            {
                "index": {"byteStart": prefix_utf16_len, "byteEnd": prefix_utf16_len + match_utf16_len},
                "features": [
                    {"$type": "app.bsky.richtext.facet#link", "uri": url},
                ],
            }
        )
    return facets or None


## Link preview & thumbnail helpers removed as per request (keep code minimal)


def post_bluesky(profile: Profile, text: str) -> Tuple[bool, str | None, str | None]:
    handle = profile.bluesky_handle or ""
    app_pw = profile.bluesky_app_password or ""
    if not handle or not app_pw or not profile.crosspost_bluesky:
        return False, "disabled_or_missing", None
    try:
        from atproto import Client  # type: ignore

        # Truncate first to avoid slicing after facet indices prepared.
        truncated = _truncate(text, BLUESKY_LIMIT)

        processed_text, facets = _build_bluesky_facets_with_richtext(truncated)
        if facets is None:
            facets = _build_bluesky_facets_manual(processed_text)

        first_url = None
        if facets:
            # Extract first link url from facets
            for fac in facets:
                for feat in fac.get("features", []):
                    if feat.get("$type") == "app.bsky.richtext.facet#link":
                        first_url = feat.get("uri")
                        break
                if first_url:
                    break

        client = Client()
        client.login(handle, app_pw)
        # send_post supports facets & embed when provided
        kwargs = {"text": processed_text}
        if facets:
            kwargs["facets"] = facets

        # No external embed; links appear via facets only.
        post = client.send_post(**kwargs)  # type: ignore[arg-type]
        uri = getattr(post, "uri", None)
        remote_url = None
        if isinstance(uri, str):
            rkey = uri.rsplit("/", 1)[-1]
            remote_url = f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else None
        return True, uri, remote_url
    except Exception as e:  # noqa: BLE001
        profile.record_crosspost_error(f"Bluesky post failed: {e.__class__.__name__}")
        return False, None, None


def post_status_cafe(profile: Profile, text: str, face: str | None = None) -> bool:
    """Programmatic login + status submit to status.cafe.

    Since there is no public API we mimic browser form posts:
      1. GET /login -> parse CSRF token (gorilla.csrf.Token)
      2. POST /check-login with name+password+token (follow redirects)
      3. GET / (home) to obtain posting form CSRF token
      4. POST /add with face (emoji) + content + gorilla.csrf.Token

    Returns (ok).
    """
    username = profile.status_cafe_username or ""
    password = profile.status_cafe_password or ""
    if not username or not password or not profile.crosspost_status_cafe:
        return False

    try:
        import httpx
        from bs4 import BeautifulSoup  # type: ignore

        # Shared client with cookie persistence
        headers = {"User-Agent": "AetherCrossposter/0.1 (+https://aether.meadow.cafe)"}
        with httpx.Client(
            base_url="https://status.cafe",
            headers=headers,
            timeout=15,
            follow_redirects=True,
        ) as client:
            # Step 1: fetch login page
            r = client.get("/login")
            if r.status_code != 200:
                profile.record_crosspost_error(f"Status.cafe login_get {r.status_code}")
                return False

            soup = BeautifulSoup(r.text, "html.parser")
            token_input = soup.find("input", {"name": "gorilla.csrf.Token"})  # type: ignore[assignment]
            # Use getattr to satisfy type checkers (BeautifulSoup dynamic attrs)
            if not token_input or not getattr(token_input, "get", lambda _x: None)("value"):
                profile.record_crosspost_error("Status.cafe token_missing")
                return False
            csrf_login = getattr(token_input, "get", lambda _x: None)("value")  # type: ignore[call-arg]

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
                return False

            # Step 3: fetch homepage for post form
            r3 = client.get("/")
            if r3.status_code != 200:
                profile.record_crosspost_error(f"Status.cafe home_get {r3.status_code}")
                return False

            soup_home = BeautifulSoup(r3.text, "html.parser")
            token_post_input = soup_home.find("form", {"action": "/add"})  # type: ignore[assignment]
            if not token_post_input:
                profile.record_crosspost_error("Status.cafe post_form_missing")
                return False
            hidden_csrf = token_post_input.find("input", {"name": "gorilla.csrf.Token"})  # type: ignore[assignment]
            if not hidden_csrf or not getattr(hidden_csrf, "get", lambda _x: None)("value"):
                profile.record_crosspost_error("Status.cafe post_token_missing")
                return False
            csrf_post = getattr(hidden_csrf, "get", lambda _x: None)("value")  # type: ignore[call-arg]

            chosen_face = (face or "").strip()
            if chosen_face and len(chosen_face) > 8:
                chosen_face = chosen_face[:8]
            content = _truncate(text, STATUS_CAFE_LIMIT)
            r4 = client.post(
                "/add",
                data={
                    "gorilla.csrf.Token": csrf_post,
                    "face": chosen_face or "🙂",  # default emoji if unset
                    "content": content,
                },
            )

            if r4.status_code not in (200, 302):
                profile.record_crosspost_error(
                    f"Status.cafe post_fail {r4.status_code}"
                )
                return False

            return True

    except Exception as e:  # noqa: BLE001
        profile.record_crosspost_error(f"Status.cafe exception: {e.__class__.__name__}")
        return False


def _post_selected_networks(
    profile: Profile,
    text: str,
    *,
    want_masto: bool,
    want_bluesky: bool,
    want_status_cafe: bool,
    status_cafe_face: Optional[str] = None,
    note=None,
) -> None:
    """Internal worker that respects per-note selections combined with profile global toggles.

    Any errors are recorded on the profile via the existing helpers.
    """
    any_error = False

    if want_masto and profile.crosspost_mastodon:
        ok, remote_id, remote_url = post_mastodon(profile, text)
        any_error = any_error or (not ok)
        if ok and note is not None:
            try:
                from aether_notes.models import NoteCrosspost  # type: ignore
                cp, created = NoteCrosspost.objects.get_or_create(note=note, network="mastodon")
                if created:
                    cp.mark_success(remote_id=remote_id, remote_url=remote_url)
            except Exception:  # pragma: no cover
                pass

    if want_bluesky and profile.crosspost_bluesky:
        ok, remote_id, remote_url = post_bluesky(profile, text)
        any_error = any_error or (not ok)
        if ok and note is not None:
            try:
                from aether_notes.models import NoteCrosspost  # type: ignore
                cp, created = NoteCrosspost.objects.get_or_create(note=note, network="bluesky")
                if created:
                    cp.mark_success(remote_id=remote_id, remote_url=remote_url)
            except Exception:  # pragma: no cover
                pass

    if want_status_cafe and getattr(profile, "crosspost_status_cafe", False):
        ok = post_status_cafe(profile, text, face=status_cafe_face)
        any_error = any_error or (not ok)

    if not any_error and (
        profile.last_crosspost_error or profile.last_crosspost_error_at
    ):
        profile.clear_crosspost_error()


def post_selected_networks_async(
    profile: Profile,
    text: str,
    *,
    want_masto: bool,
    want_bluesky: bool,
    want_status_cafe: bool,
    status_cafe_face: Optional[str] = None,
    note=None,
) -> None:
    """Fire-and-forget thread that posts only to networks the user selected on this note.

    Combines per-note selections with global profile toggles so a disabled global setting never posts.
    """
    threading.Thread(
        target=_post_selected_networks,
        kwargs=dict(
            profile=profile,
            text=text,
            want_masto=want_masto,
            want_bluesky=want_bluesky,
            want_status_cafe=want_status_cafe,
            status_cafe_face=status_cafe_face,
            note=note,
        ),
        daemon=True,
    ).start()
