from __future__ import annotations
from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("settings/", views.settings_view, name="settings"),
    path("check-username/", views.check_username, name="check_username"),
    path("clear-error/", views.clear_crosspost_error, name="clear_error"),
    path("test-mastodon/", views.test_mastodon, name="test_mastodon"),
    path("test-bluesky/", views.test_bluesky, name="test_bluesky"),
    # Mastodon OAuth
    path("mastodon/start/", views.mastodon_oauth_start, name="mastodon_oauth_start"),
    path("mastodon/callback/", views.mastodon_oauth_callback, name="mastodon_oauth_callback"),
]
