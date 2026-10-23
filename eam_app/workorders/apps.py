from django.apps import AppConfig


class WorkordersConfig(AppConfig):
    name = 'workorders'

    def ready(self):
        import workorders.signals  # noqa
