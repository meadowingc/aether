from django.apps import AppConfig
from django.db.backends.signals import connection_created


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        # Import signals to ensure profile auto-creation
        from . import signals  # noqa: F401

        # Register a handler to set SQLite pragmas AFTER the first real connection
        # (avoids touching the DB during app initialization; removes runtime warning).
        def _set_sqlite_pragmas(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                with connection.cursor() as c:
                    c.execute("PRAGMA journal_mode=WAL;")
                    c.execute("PRAGMA synchronous=NORMAL;")
        connection_created.connect(_set_sqlite_pragmas, dispatch_uid="accounts_sqlite_pragmas")
