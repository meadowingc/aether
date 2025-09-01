from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("about/", views.about, name="about"),
    path("create-note/", views.create_note, name="create_note"),
    path("witness/", views.witness, name="witness"),
    path("flag-note/", views.flag_note, name="flag_note"),
    path("delete-note/", views.delete_note, name="delete_note"),
]
