import logging
from datetime import datetime
from urllib.parse import quote
from django.http import HttpResponseRedirect, FileResponse, HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.authentication import SessionAuthentication

from analytics.services import DashboardCacheService
from analytics.models import ExportJob
from analytics.report_services import (
    AssetValuationEngine,
    MaintenancePerformanceEngine,
    SparePartsValuationEngine,
    CostSummaryEngine
)
from analytics.export_engine import MinIOStorageService, REPORT_BUCKET_NAME
from analytics.tasks import generate_export_report

logger = logging.getLogger(__name__)


def success_response(data=None, message="Success", http_status=status.HTTP_200_OK):
    return Response({
        "success": True,
        "message": message,
        "data": data
    }, status=http_status)


def error_response(code: str, message: str, http_status=status.HTTP_400_BAD_REQUEST):
    return Response({
        "success": False,
        "error": {
            "code": code,
            "message": message
        }
    }, status=http_status)


def check_report_permission(user, report_type: str) -> bool:
    """
    Enforces Section 5 RBAC rules:
    - Superusers / Admins / Maintenance Managers: Full access to all 4 reports.
    - Warehouse Keepers: Access to SPARE_PARTS.
    - Technicians: Access to hours and work orders, forbidden from ASSET_VALUATION.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True

    role_names = set(r.name.upper() for r in user.roles.all()) if hasattr(user, 'roles') else set()
    if any(r in role_names for r in ['ADMIN', 'TENANT_ADMIN', 'MAINTENANCE_MANAGER', 'SYSTEM_ADMIN']):
        return True

    perms = set()
    if hasattr(user, 'roles'):
        for role in user.roles.prefetch_related('permissions').all():
            for perm in role.permissions.all():
                perms.add(perm.id)
    if 'system:admin' in perms or 'reports:read' in perms or 'audit_logs:read' in perms:
        return True

    # Role specific boundaries
    if report_type == 'SPARE_PARTS' and any('WAREHOUSE' in r or 'KEEPER' in r for r in role_names):
        return True
    if report_type == 'ASSET_VALUATION' and any('TECHNICIAN' in r for r in role_names):
        return False
    if report_type in ['MAINTENANCE_PERFORMANCE', 'SPARE_PARTS', 'COST_SUMMARY'] and any('TECHNICIAN' in r for r in role_names):
        return True

    return True


class DashboardSummaryView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return error_response("NO_TENANT", "Tenant not associated with user")

        summary_data = DashboardCacheService.get_summary(tenant)
        return success_response(summary_data)


class DashboardTrendsView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return error_response("NO_TENANT", "Tenant not associated with user")

        trends_data = DashboardCacheService.get_trends(tenant)
        return success_response(trends_data)


class DashboardActivityFeedView(APIView):
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return error_response("NO_TENANT", "Tenant not associated with user")

        activities = DashboardCacheService.get_activity_feed(tenant)
        return success_response({"activities": activities})


# =========================================================================
# Phase 10.3: Enterprise Reports & Export Engine Endpoints
# =========================================================================

class ReportPreviewView(APIView):
    """
    POST /api/v1/reports/preview/
    Returns live aggregated summary KPIs, chart series, and preview data (max 50 rows).
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return error_response("NO_TENANT", "Tenant not associated with user")

        data = request.data or {}
        report_type = data.get('reportType', 'ASSET_VALUATION').upper()
        filters = data.get('filters', {})

        if not check_report_permission(request.user, report_type):
            return error_response(
                "FORBIDDEN_REPORT_ACCESS",
                "Bạn không có quyền truy cập phân hệ báo cáo tài chính này.",
                http_status=status.HTTP_403_FORBIDDEN
            )

        try:
            if report_type == 'ASSET_VALUATION':
                result = AssetValuationEngine.get_asset_valuation_data(
                    tenant=tenant,
                    category_id=filters.get('categoryId'),
                    location_id=filters.get('locationId'),
                    search=filters.get('search')
                )
                preview_items = result.get('items', [])[:50]
                result['items'] = preview_items

            elif report_type == 'MAINTENANCE_PERFORMANCE':
                result = MaintenancePerformanceEngine.get_performance_data(
                    tenant=tenant,
                    date_from=datetime.strptime(filters['dateFrom'], '%Y-%m-%d').date() if filters.get('dateFrom') else None,
                    date_to=datetime.strptime(filters['dateTo'], '%Y-%m-%d').date() if filters.get('dateTo') else None,
                    location_id=filters.get('locationId')
                )
                preview_items = result.get('items', [])[:50]
                result['items'] = preview_items

            elif report_type == 'SPARE_PARTS':
                result = SparePartsValuationEngine.get_spare_parts_data(
                    tenant=tenant,
                    date_from=datetime.strptime(filters['dateFrom'], '%Y-%m-%d').date() if filters.get('dateFrom') else None,
                    date_to=datetime.strptime(filters['dateTo'], '%Y-%m-%d').date() if filters.get('dateTo') else None,
                    search=filters.get('search')
                )
                result['parts'] = result.get('parts', [])[:50]
                result['transactions'] = result.get('transactions', [])[:50]

            elif report_type == 'COST_SUMMARY':
                result = CostSummaryEngine.get_cost_summary_data(
                    tenant=tenant,
                    date_from=datetime.strptime(filters['dateFrom'], '%Y-%m-%d').date() if filters.get('dateFrom') else None,
                    date_to=datetime.strptime(filters['dateTo'], '%Y-%m-%d').date() if filters.get('dateTo') else None,
                    cost_center=filters.get('costCenter'),
                    include_capex=filters.get('includeCapex', False)
                )
                result['costCenters'] = result.get('costCenters', [])[:50]

            else:
                return error_response("INVALID_REPORT_TYPE", f"Loại báo cáo không hợp lệ: {report_type}")

            return success_response(result)

        except Exception as e:
            logger.exception(f"Error generating report preview: {e}")
            return error_response("PREVIEW_ERROR", f"Lỗi tạo bản xem trước: {str(e)}")


class ReportExportView(APIView):
    """
    POST /api/v1/reports/export/
    Initiates asynchronous export pipeline with Celery, enforcing max 3 concurrent jobs per tenant.
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return error_response("NO_TENANT", "Tenant not associated with user")

        data = request.data or {}
        report_type = data.get('reportType', 'ASSET_VALUATION').upper()
        file_format = data.get('fileFormat', 'XLSX').upper()
        filters = data.get('filters', {})

        if not check_report_permission(request.user, report_type):
            return error_response(
                "FORBIDDEN_REPORT_EXPORT",
                "Bạn không có quyền xuất phân hệ báo cáo này.",
                http_status=status.HTTP_403_FORBIDDEN
            )

        # Rule 7: Concurrency Limit (Max 3 concurrent jobs per tenant)
        active_jobs_count = ExportJob.all_objects.filter(
            tenant=tenant,
            status__in=['PENDING', 'PROCESSING']
        ).count()

        if active_jobs_count >= 3:
            return Response({
                "success": False,
                "error": {
                    "code": "CONCURRENT_EXPORT_LIMIT_EXCEEDED",
                    "message": "Bạn đang có 3 tác vụ xuất đang xử lý. Vui lòng chờ tác vụ trước hoàn tất."
                }
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Initialize ExportJob
        job = ExportJob.all_objects.create(
            tenant=tenant,
            user=request.user,
            report_type=report_type,
            file_format=file_format,
            filter_params=filters,
            status='PENDING',
            progress_percent=0,
            file_name=f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_format.lower()}"
        )

        # Enqueue Celery task
        try:
            generate_export_report.delay(str(job.id))
        except Exception as e:
            logger.warning(f"Celery dispatch failed, running synchronous fallback: {e}")
            generate_export_report(str(job.id))

        return Response({
            "success": True,
            "data": {
                "jobId": str(job.id),
                "status": "PENDING",
                "message": "Yêu cầu xuất báo cáo đã được tiếp nhận và đang xử lý ngầm."
            }
        }, status=status.HTTP_202_ACCEPTED)


class ReportExportJobDetailView(APIView):
    """
    GET /api/v1/reports/export-jobs/<uuid:id>/
    Polls job progress and returns Presigned URL (24h) when completed.
    Enforces strict Multi-Tenant isolation (chống IDOR).
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return error_response("NO_TENANT", "Tenant not associated with user")

        try:
            # Multi-Tenant isolation: Must belong to requesting user's tenant
            job = ExportJob.all_objects.get(id=id, tenant=tenant)
        except ExportJob.DoesNotExist:
            return error_response(
                "JOB_NOT_FOUND",
                "Tác vụ xuất không tồn tại hoặc bạn không có quyền truy cập.",
                http_status=status.HTTP_404_NOT_FOUND
            )

        download_url = None
        friendly_filename = job.file_name or f"{job.report_type}_{str(job.id)[:8]}.{job.file_format.lower()}"
        if job.status == 'COMPLETED' and job.minio_object_key:
            try:
                download_url = MinIOStorageService.generate_presigned_url(
                    job.minio_object_key,
                    expires_hours=24,
                    response_filename=friendly_filename
                )
            except Exception as e:
                logger.error(f"Failed to generate presigned URL for job {job.id}: {e}")

        return success_response({
            "jobId": str(job.id),
            "reportType": job.report_type,
            "fileFormat": job.file_format,
            "status": job.status,
            "progressPercent": job.progress_percent,
            "fileName": friendly_filename,
            "fileSizeBytes": job.file_size_bytes,
            "downloadUrl": download_url,
            "expiresAt": job.expires_at.isoformat() if job.expires_at else None,
            "errorMessage": job.error_message
        })


class ReportExportJobDownloadView(APIView):
    """
    GET /api/v1/reports/export-jobs/<uuid:id>/download/
    Direct download redirect with enforced Content-Disposition attachment filename.
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return error_response("NO_TENANT", "Tenant not associated with user")

        try:
            job = ExportJob.all_objects.get(id=id, tenant=tenant)
        except ExportJob.DoesNotExist:
            return error_response(
                "JOB_NOT_FOUND",
                "Tác vụ xuất không tồn tại hoặc bạn không có quyền truy cập.",
                http_status=status.HTTP_404_NOT_FOUND
            )

        if job.status != 'COMPLETED' or not job.minio_object_key:
            return error_response(
                "JOB_NOT_READY",
                "Tệp báo cáo chưa hoàn tất hoặc đã hết hạn.",
                http_status=status.HTTP_400_BAD_REQUEST
            )

        client = MinIOStorageService.get_client()
        try:
            minio_obj = client.get_object(REPORT_BUCKET_NAME, job.minio_object_key)
            file_data = minio_obj.read()
            minio_obj.close()
            minio_obj.release_conn()
        except Exception as e:
            logger.error(f"Failed to fetch object {job.minio_object_key} from MinIO: {e}")
            return error_response(
                "FILE_FETCH_ERROR",
                "Không thể tải tệp từ kho lưu trữ.",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        content_types = {
            'XLSX': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'PDF': 'application/pdf',
            'CSV': 'text/csv; charset=utf-8'
        }
        content_type = content_types.get(job.file_format.upper(), 'application/octet-stream')

        friendly_filename = job.file_name or f"{job.report_type}_{str(job.id)[:8]}.{job.file_format.lower()}"
        if not friendly_filename.lower().endswith(f".{job.file_format.lower()}"):
            friendly_filename = f"{friendly_filename}.{job.file_format.lower()}"

        # Clean ASCII filename fallback for Content-Disposition
        safe_ascii_filename = friendly_filename.encode('ascii', 'ignore').decode('ascii') or f"report.{job.file_format.lower()}"

        response = HttpResponse(
            file_data,
            content_type=content_type
        )
        response['Content-Disposition'] = f'attachment; filename="{safe_ascii_filename}"; filename*=UTF-8\'\'{quote(friendly_filename)}'
        response['Content-Length'] = len(file_data)
        return response


class ReportExportJobHistoryView(APIView):
    """
    GET /api/v1/reports/export-jobs/
    Returns recent export jobs history for the user and tenant.
    """
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            return error_response("NO_TENANT", "Tenant not associated with user")

        jobs = ExportJob.all_objects.filter(tenant=tenant).order_by('-created_at')[:20]

        data = []
        for j in jobs:
            data.append({
                "jobId": str(j.id),
                "reportType": j.report_type,
                "reportTypeName": j.get_report_type_display(),
                "fileFormat": j.file_format,
                "status": j.status,
                "progressPercent": j.progress_percent,
                "fileName": j.file_name,
                "fileSizeBytes": j.file_size_bytes,
                "createdAt": j.created_at.strftime('%d/%m/%Y %H:%M'),
                "expiresAt": j.expires_at.strftime('%d/%m/%Y %H:%M') if j.expires_at else None
            })

        return success_response(data)
