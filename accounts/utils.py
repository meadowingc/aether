from __future__ import annotations
import time
from functools import wraps
from typing import Callable, Any, Optional

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

def client_ip(request: HttpRequest) -> str:
    # Basic; can be extended with X-Forwarded-For if trusted proxy
    return request.META.get("REMOTE_ADDR") or "0.0.0.0"

def _cache_key(prefix: str, ident: str) -> str:
    return f"rl:{prefix}:{ident}"

def rate_limited(prefix: str, limit: int, window_seconds: int, key_func: Callable[[HttpRequest], str] = client_ip):
    """
    Very small in-process rate limiter (best-effort; not perfectly atomic).
    Tracks a sliding window bucket expiry.

    If exceeded returns 429 JSON (if AJAX-like) else plain HttpResponse.

    window_seconds: size of window.
    limit: max allowed requests inside window.
    """
    def decorator(view):
        @wraps(view)
        def wrapper(request: HttpRequest, *args, **kwargs):
            ident = key_func(request)
            k = _cache_key(prefix, ident)
            data: Optional[dict[str, Any]] = cache.get(k)
            now = time.time()
            if not data or data.get("exp", 0) <= now:
                data = {"count": 0, "exp": now + window_seconds}
            data["count"] += 1
            cache.set(k, data, timeout=window_seconds)
            if data["count"] > limit:
                # Exceeded
                if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.headers.get("accept", "").startswith("application/json"):
                    return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)
                return HttpResponse("Too Many Requests", status=429)
            return view(request, *args, **kwargs)
        return wrapper
    return decorator

def remaining_requests(prefix: str, request: HttpRequest, limit: int, window_seconds: int, key_func: Callable[[HttpRequest], str] = client_ip) -> int:
    ident = key_func(request)
    k = _cache_key(prefix, ident)
    data = cache.get(k)
    if not data:
        return limit
    return max(0, limit - int(data.get("count", 0)))
