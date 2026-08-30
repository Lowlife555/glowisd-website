from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'
    verbose_name = '网站核心'

    def ready(self):
        from . import signals  # noqa: F401
