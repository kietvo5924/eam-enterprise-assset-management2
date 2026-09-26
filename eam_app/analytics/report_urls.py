from django.urls import path, re_path
from analytics.views import (
    ReportPreviewView,
    ReportExportView,
    ReportExportJobDetailView,
    ReportExportJobHistoryView,
    ReportExportJobDownloadView
)

urlpatterns = [
    re_path(r'^preview/?$', ReportPreviewView.as_view(), name='report_preview'),
    re_path(r'^export/?$', ReportExportView.as_view(), name='report_export'),
    re_path(r'^export-jobs/(?P<id>[0-9a-fA-F-]+)/download(?:/(?P<filename>[^/]+))?/?$', ReportExportJobDownloadView.as_view(), name='report_export_job_download'),
    re_path(r'^export-jobs/(?P<id>[0-9a-fA-F-]+)/?$', ReportExportJobDetailView.as_view(), name='report_export_job_detail'),
    re_path(r'^export-jobs/?$', ReportExportJobHistoryView.as_view(), name='report_export_job_history'),
]
