from django.apps import AppConfig


class AssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assistant'
    verbose_name = 'Intelligent AI Assistant (RAG)'

    def ready(self):
        try:
            import assistant.auto_ingest  # Register post_save / post_delete signals
            from assistant.auto_ingest import start_auto_ingestion_loop
            start_auto_ingestion_loop(interval_seconds=60)
            from assistant.views import load_persisted_safety_config
            load_persisted_safety_config()
        except Exception:
            pass
