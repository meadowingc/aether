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
    path("test-status-cafe/", views.test_status_cafe, name="test_status_cafe"),
    path("test-tumblr/", views.test_tumblr, name="test_tumblr"),
    path("test-piclog-blue/", views.test_piclog_blue, name="test_piclog_blue"),
    # Mastodon OAuth
    path("mastodon/start/", views.mastodon_oauth_start, name="mastodon_oauth_start"),
    path("mastodon/callback/", views.mastodon_oauth_callback, name="mastodon_oauth_callback"),
    # Tumblr OAuth
    path("tumblr/start/", views.tumblr_oauth_start, name="tumblr_oauth_start"),
    path("tumblr/callback/", views.tumblr_oauth_callback, name="tumblr_oauth_callback"),
    # Public archive/profile
    path("u/<str:username>/", views.user_archive, name="user_archive"),
]
