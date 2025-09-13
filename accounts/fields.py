from __future__ import annotations
import base64
import hashlib
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _get_fernet() -> Fernet:
    # Derive a 32-byte key from SECRET_KEY (stable; rotate by adding salt/version if needed later)
    key_material = hashlib.sha256((settings.SECRET_KEY).encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(key_material)
    return Fernet(key)


class EncryptedTextField(models.TextField):
    """
    Minimal symmetric encrypted text field using Fernet.
    Stores base64 token; transparently returns plaintext in Python layer.

    NOTE: Not searchable; length increases (~ +100 bytes).
    """

    def from_db_value(self, value: Optional[str], expression, connection) -> Optional[str]:
        if value in (None, ""):
            return value
        f = _get_fernet()
        try:
            return f.decrypt(value.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError):
            # If decryption fails, return raw (avoid hard failure)
            return value

    def to_python(self, value: Any) -> Any:
        # Already decrypted or empty
        return value

    def get_prep_value(self, value: Any) -> Any:
        if value in (None, ""):
            return value
        if not isinstance(value, str):
            value = str(value)
        f = _get_fernet()
        token = f.encrypt(value.encode("utf-8"))
        return token.decode("utf-8")
