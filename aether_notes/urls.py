from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("about/", views.about, name="about"),
    path("create-note/", views.create_note, name="create_note"),
    path("witness/", views.witness, name="witness"),
    path("flag-note/", views.flag_note, name="flag_note"),
    path("delete-note/", views.delete_note, name="delete_note"),
    path("drafts/", views.drafts_list, name="drafts_list"),
    path("drafts/<int:pk>/edit/", views.edit_draft, name="edit_draft"),
    path("queue/", views.queue_list, name="queue_list"),
    path("queue/settings/", views.update_queue_settings, name="update_queue_settings"),
    path("queue/toggle/", views.toggle_queue, name="toggle_queue"),
    path("queue/<int:pk>/edit/", views.edit_queue_item, name="edit_queue_item"),
    path(
        "queue/<int:pk>/move/<str:direction>/",
        views.move_queue_item,
        name="move_queue_item",
    ),
    path("queue/<int:pk>/delete/", views.delete_queue_item, name="delete_queue_item"),
]
