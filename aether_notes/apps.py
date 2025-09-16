from django.apps import AppConfig


class AetherNotesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aether_notes'
    
    def ready(self):
        import aether_notes.db_signals
