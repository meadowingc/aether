from __future__ import annotations
import time
from typing import Callable
from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

LOGIN_PATH_SUFFIX = "/account/login/"  # two_factor default (project includes tf urls at root)

class RateLimitAuthMiddleware:
    """
    Lightweight IP-based rate limit for login POST submissions.
    Uses LocMemCache; for multi-process deploy swap to shared backend.

    Settings:
        AUTH_LOGIN_RATE_LIMIT = {"limit": 5, "window": 60}
    Response: HTTP 429 (JSON if ajax / Accept: application/json)
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        conf = getattr(settings, "AUTH_LOGIN_RATE_LIMIT", {"limit": 5, "window": 60})
        self.limit: int = int(conf.get("limit", 5))
        self.window: int = int(conf.get("window", 60))

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Only act on POST to login endpoint
        if (
            request.method == "POST"
            and request.path.endswith(LOGIN_PATH_SUFFIX)
            and self.limit > 0
            and self.window > 0
        ):
            ip = request.META.get("REMOTE_ADDR") or "0.0.0.0"
            key = f"rl:login:{ip}"
            data = cache.get(key)
            now = time.time()
            if not data or data.get("exp", 0) <= now:
                data = {"count": 0, "exp": now + self.window}
            data["count"] += 1
            cache.set(key, data, timeout=self.window)
            if data["count"] > self.limit:
                if self._wants_json(request):
                    return JsonResponse({"ok": False, "error": "rate_limited"}, status=429)
                return HttpResponse("Too Many Login Attempts", status=429)

        return self.get_response(request)

    @staticmethod
    def _wants_json(request: HttpRequest) -> bool:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return True
        accept = request.headers.get("accept", "")
        return "application/json" in accept.lower()
