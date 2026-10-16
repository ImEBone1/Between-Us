from django.apps import AppConfig


class CouplesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "couples"

    def ready(self):
        import couples.signals  # noqa: F401

