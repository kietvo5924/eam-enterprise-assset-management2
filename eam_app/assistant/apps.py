from django.apps import AppConfig


class AssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assistant'
    verbose_name = 'Intelligent AI Assistant (RAG)'

    def ready(self):
        try:
            from assistant.auto_ingest import start_auto_ingestion_loop
            start_auto_ingestion_loop(interval_seconds=60)
        except Exception:
            pass
