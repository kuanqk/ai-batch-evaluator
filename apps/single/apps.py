from django.apps import AppConfig


class SingleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.single"
    label = "single"
    verbose_name = "Одиночная оценка"
