from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):  # pragma: no cover - import side effects
        # Import signals so that Profile auto-creation is registered.
        # Avoid circular imports by importing inside method.
        try:
            import accounts.signals  # noqa: F401
        except Exception:
            # Failing silently here prevents startup crash; log in real app if needed.
            pass
