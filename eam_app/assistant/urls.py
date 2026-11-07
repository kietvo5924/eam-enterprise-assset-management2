from django.urls import path
from . import views

urlpatterns = [
    # Technician Field Assistant & Chat
    path('chat/', views.AssistantChatView.as_view(), name='assistant_chat'),
    path('feedback/', views.AssistantFeedbackView.as_view(), name='assistant_feedback'),
    path('create-work-order-draft/', views.AssistantCreateWorkOrderDraftView.as_view(), name='assistant_create_work_order_draft'),
    path('offline-pack/<uuid:asset_id>/', views.AssistantOfflinePackView.as_view(), name='assistant_offline_pack'),

    # Admin Knowledge Management
    path('admin/qa-list/', views.AssistantAdminQAListView.as_view(), name='assistant_admin_qa_list'),
    path('admin/qa/', views.AssistantAdminQACreateUpdateView.as_view(), name='assistant_admin_qa_save'),
    path('admin/qa/<uuid:id>/', views.AssistantAdminQADeleteView.as_view(), name='assistant_admin_qa_delete'),
    path('admin/curation-queue/', views.AssistantAdminCurationQueueView.as_view(), name='assistant_admin_curation_queue'),
    path('admin/curation-queue/<uuid:id>/approve/', views.AssistantAdminCurationApproveView.as_view(), name='assistant_admin_curation_approve'),
    path('admin/documents/<uuid:doc_id>/', views.AssistantAdminDocumentDetailView.as_view(), name='assistant_admin_doc_detail'),
    path('admin/upload-document/', views.AssistantAdminUploadDocumentView.as_view(), name='assistant_admin_upload_document'),
    path('admin/reindex/', views.AssistantAdminReindexView.as_view(), name='assistant_admin_reindex'),
    path('admin/safety-config/', views.AssistantAdminSafetyConfigView.as_view(), name='assistant_admin_safety_config'),
]
