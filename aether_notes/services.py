from __future__ import annotations

from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from accounts.social import post_selected_networks, post_selected_networks_async

from .images import compress_for_storage, convert_for_bluesky, process_uploaded_image
from .models import Note


@dataclass(frozen=True)
class CrosspostSelection:
    mastodon: bool = False
    bluesky: bool = False
    status_cafe: bool = False
    tumblr: bool = False
    piclog_blue: bool = False
    status_cafe_face: str | None = None

    @classmethod
    def from_post_data(cls, data) -> "CrosspostSelection":
        return cls(
            mastodon=bool(data.get("xp_mastodon")),
            bluesky=bool(data.get("xp_bluesky")),
            status_cafe=bool(data.get("xp_status_cafe")),
            tumblr=bool(data.get("xp_tumblr")),
            piclog_blue=bool(data.get("xp_piclog_blue")),
            status_cafe_face=(data.get("xp_status_cafe_face") or "").strip() or None,
        )


@dataclass
class PreparedImages:
    hq: bytes | None = None
    bluesky: bytes | None = None
    compressed: bytes | None = None
    alt: str = ""


def save_unpublished_note(
    note: Note,
    text: str,
    *,
    uploaded_file=None,
    image_alt: str = "",
    remove_image: bool = False,
) -> None:
    note.text = text
    note.is_draft = True
    files_to_delete = []
    if uploaded_file:
        old_files = [
            (field.storage, field.name)
            for field in (note.image, note.image_hq)
            if field and field.name
        ]
        raw_bytes = uploaded_file.read()
        if raw_bytes:
            compressed, hq, _ = process_uploaded_image(raw_bytes)
            filename = uploaded_file.name or "image.jpg"
            if not filename.lower().endswith((".jpg", ".jpeg")):
                stem = filename.rsplit(".", 1)[0] if "." in filename else filename
                filename = f"{stem}.jpg"
            note.image.save(filename, ContentFile(compressed), save=False)
            note.image_hq.save(f"hq_{filename}", ContentFile(hq), save=False)
            note.image_alt = image_alt.strip()[:1000]
            new_names = {note.image.name, note.image_hq.name}
            files_to_delete = [
                (storage, name)
                for storage, name in old_files
                if name not in new_names
            ]
    elif remove_image:
        files_to_delete = [
            (field.storage, field.name)
            for field in (note.image, note.image_hq)
            if field and field.name
        ]
        note.image = None
        note.image_hq = None
        note.image_alt = ""
    elif note.image:
        note.image_alt = image_alt.strip()[:1000]
    note.save()
    for storage, name in files_to_delete:
        if storage.exists(name):
            storage.delete(name)


def _prepare_stored_image(note: Note) -> PreparedImages:
    if not note.image or not note.image_hq:
        return PreparedImages(alt=note.image_alt or "")

    note.image_hq.open("rb")
    try:
        hq = note.image_hq.read()
    finally:
        note.image_hq.close()

    if not hq:
        return PreparedImages(alt=note.image_alt or "")
    return PreparedImages(
        hq=hq,
        bluesky=convert_for_bluesky(hq),
        compressed=compress_for_storage(hq),
        alt=note.image_alt or "",
    )


def publish_note(
    note: Note,
    *,
    user,
    selection: CrosspostSelection,
    prepared_images: PreparedImages | None = None,
    async_crossposts: bool,
) -> None:
    images = prepared_images if prepared_images is not None else _prepare_stored_image(note)

    note.is_draft = False
    note.pub_date = timezone.now()
    if note.image_hq:
        note.image_hq.delete(save=False)
        note.image_hq = None
    note.save()

    if not user or not hasattr(user, "profile"):
        return
    if not any(
        (
            selection.mastodon,
            selection.bluesky,
            selection.status_cafe,
            selection.tumblr,
            selection.piclog_blue,
        )
    ):
        return

    post = post_selected_networks_async if async_crossposts else post_selected_networks
    callback = lambda: post(
        user.profile,
        note.text,
        want_masto=selection.mastodon,
        want_bluesky=selection.bluesky,
        want_status_cafe=selection.status_cafe,
        want_tumblr=selection.tumblr,
        want_piclog_blue=selection.piclog_blue,
        status_cafe_face=selection.status_cafe_face,
        note=note,
        image_hq_bytes=images.hq,
        image_bluesky_bytes=images.bluesky,
        image_compressed_bytes=images.compressed,
        image_alt=images.alt,
    )
    transaction.on_commit(callback)
