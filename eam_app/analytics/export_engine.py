import os
import csv
import logging
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Tuple, List, Dict, Any, Generator, Optional

from django.conf import settings
from django.utils import timezone
from minio import Minio

from analytics.models import ExportJob
from analytics.report_services import (
    AssetValuationEngine,
    MaintenancePerformanceEngine,
    SparePartsValuationEngine,
    CostSummaryEngine,
    round_vnd,
    parse_date_safe
)

logger = logging.getLogger(__name__)

REPORT_BUCKET_NAME = "eam-reports"


def sanitize_cell_value(value: Any) -> Any:
    """
    Rule 9: Anti-Formula & CSV Injection Guardrail.
    If a string starts with '=', '+', '-', '@', '\t', or '\r',
    prepends a single quote "'" to enforce plain text rendering in Excel/CSV.
    """
    if isinstance(value, str) and value:
        if value[0] in ('=', '+', '-', '@', '\t', '\r'):
            return f"'{value}"
    return value


class MinIOStorageService:
    """
    Handles storage interactions with MinIO:
    Private bucket creation, file upload, presigned URL generation, and auto-purging.
    """

    @classmethod
    def get_client(cls) -> Minio:
        return Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )

    @classmethod
    def ensure_bucket_exists(cls, client: Minio, bucket_name: str = REPORT_BUCKET_NAME):
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)

    @classmethod
    def upload_file(cls, local_path: str, object_name: str, content_type: str = "application/octet-stream") -> int:
        client = cls.get_client()
        cls.ensure_bucket_exists(client, REPORT_BUCKET_NAME)
        file_size = os.path.getsize(local_path)
        client.fput_object(
            bucket_name=REPORT_BUCKET_NAME,
            object_name=object_name,
            file_path=local_path,
            content_type=content_type
        )
        return file_size

    @classmethod
    def generate_presigned_url(cls, object_name: str, expires_hours: int = 24, response_filename: Optional[str] = None) -> str:
        client = cls.get_client()
        response_headers = None
        if response_filename:
            response_headers = {
                'response-content-disposition': f'attachment; filename="{response_filename}"'
            }
        url = client.presigned_get_object(
            bucket_name=REPORT_BUCKET_NAME,
            object_name=object_name,
            expires=timedelta(hours=expires_hours),
            response_headers=response_headers
        )
        return url

    @classmethod
    def delete_file(cls, object_name: str):
        try:
            client = cls.get_client()
            client.remove_object(REPORT_BUCKET_NAME, object_name)
        except Exception as e:
            logger.warning(f"Failed to delete MinIO object {object_name}: {e}")


class ExportEngineService:
    """
    Generates report data, streams to XLSX/PDF/CSV, sanitizes formula characters,
    and uploads to MinIO.
    """

    @classmethod
    def build_object_key(cls, tenant_id: str, job_id: str, extension: str) -> str:
        now = timezone.now()
        year = now.strftime('%Y')
        month = now.strftime('%m')
        return f"{tenant_id}/{year}/{month}/{job_id}.{extension.lower()}"

    @classmethod
    def generate_and_upload(cls, job: ExportJob, progress_callback=None) -> Tuple[str, int, str]:
        """
        Executes report generation pipeline:
        1. Query data with chunking
        2. Stream to temp file
        3. Upload to MinIO
        Returns (object_key, file_size_bytes, download_url)
        """
        if progress_callback:
            progress_callback(10)

        report_type = job.report_type
        file_format = job.file_format.upper()
        filters = job.filter_params or {}

        # 1. Fetch headers and row generator
        headers, row_generator, filename_prefix = cls._get_report_data_stream(job.tenant, report_type, filters)

        if progress_callback:
            progress_callback(30)

        # 2. Generate local temp file
        ext = file_format.lower()
        temp_dir = tempfile.gettempdir()
        temp_filename = f"{filename_prefix}_{job.id}.{ext}"
        local_path = os.path.join(temp_dir, temp_filename)

        try:
            if file_format == 'XLSX':
                cls._export_xlsx(headers, row_generator, local_path, report_type)
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif file_format == 'PDF':
                cls._export_pdf(headers, row_generator, local_path, report_type)
                content_type = "application/pdf"
            else:  # CSV
                cls._export_csv(headers, row_generator, local_path)
                content_type = "text/csv; charset=utf-8"

            if progress_callback:
                progress_callback(75)

            # 3. Upload to MinIO
            object_key = cls.build_object_key(str(job.tenant_id), str(job.id), ext)
            file_size = MinIOStorageService.upload_file(local_path, object_key, content_type=content_type)

            now = timezone.now()
            friendly_filename = f"{filename_prefix}_{now.strftime('%Y%m%d_%H%M%S')}.{ext}"
            job.file_name = friendly_filename

            if progress_callback:
                progress_callback(90)

            # 4. Generate Presigned URL with Content-Disposition attachment filename
            presigned_url = MinIOStorageService.generate_presigned_url(
                object_key,
                expires_hours=24,
                response_filename=friendly_filename
            )

            return object_key, file_size, presigned_url
        finally:
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except Exception:
                    pass

    @classmethod
    def _get_report_data_stream(cls, tenant, report_type: str, filters: dict):
        if report_type == 'ASSET_VALUATION':
            return cls._stream_asset_valuation(tenant, filters)
        elif report_type == 'MAINTENANCE_PERFORMANCE':
            return cls._stream_maintenance_performance(tenant, filters)
        elif report_type == 'SPARE_PARTS':
            return cls._stream_spare_parts(tenant, filters)
        elif report_type == 'COST_SUMMARY':
            return cls._stream_cost_summary(tenant, filters)
        else:
            raise ValueError(f"Unknown report type: {report_type}")

    @classmethod
    def _stream_asset_valuation(cls, tenant, filters: dict):
        headers = [
            "Mã Thiết Bị",
            "Tên Thiết Bị",
            "Danh Mục",
            "Vị Trí / Phân Xưởng",
            "Ngày Đưa Vào SD",
            "Nguyên Giá Ban Đầu (VNĐ)",
            "Đại Tu Vốn Hóa CAPEX (VNĐ)",
            "Nguyên Giá Mới Sau Vốn Hóa (VNĐ)",
            "Giá Trị Thanh Lý Ước Tính (VNĐ)",
            "Khấu Hao Lũy Kế (VNĐ)",
            "Giá Trị Sổ Sách Còn Lại (VNĐ)",
            "Trạng Thái Tài Chính",
            "Chi Phí OPEX Tích Lũy (VNĐ)",
            "Tỷ Lệ RRR (%)",
            "Kiến Nghị Thanh Lý"
        ]

        data = AssetValuationEngine.get_asset_valuation_data(
            tenant=tenant,
            category_id=filters.get('categoryId'),
            location_id=filters.get('locationId'),
            search=filters.get('search')
        )

        def row_generator():
            for item in data['items']:
                yield [
                    sanitize_cell_value(item['serialNumber']),
                    sanitize_cell_value(item['name']),
                    sanitize_cell_value(item['categoryName']),
                    sanitize_cell_value(item['locationName']),
                    item['purchaseDate'],
                    int(item['originalCost']),
                    int(item['capexCost']),
                    int(item['totalCostBasis']),
                    int(item['salvageValue']),
                    int(item['accumulatedDepreciation']),
                    int(item['netBookValue']),
                    sanitize_cell_value(item['financialStatus']),
                    int(item['accumulatedOpex']),
                    f"{item['rrrPercent']}%",
                    sanitize_cell_value(item['recommendation'])
                ]

        return headers, row_generator(), "BaoCao_DinhGia_KhauHaoTaiSan"

    @classmethod
    def _stream_maintenance_performance(cls, tenant, filters: dict):
        headers = [
            "Mã WO",
            "Tiêu Đề",
            "Tài Sản",
            "Loại Công Việc",
            "Mức Độ Ưu Tiên",
            "Trạng Thái",
            "Kỹ Thuật Viên",
            "Hạn Hoàn Thành",
            "Thời Điểm Hoàn Thành",
            "Thời Lượng (Giờ)",
            "Lý Do Miễn Trừ Trùng Lặp"
        ]

        data = MaintenancePerformanceEngine.get_performance_data(
            tenant=tenant,
            date_from=parse_date_safe(filters.get('dateFrom')),
            date_to=parse_date_safe(filters.get('dateTo')),
            location_id=filters.get('locationId')
        )

        def row_generator():
            for item in data['items']:
                yield [
                    sanitize_cell_value(item['id'][:8]),
                    sanitize_cell_value(item['title']),
                    sanitize_cell_value(item['assetName']),
                    sanitize_cell_value(item['type']),
                    sanitize_cell_value(item['priority']),
                    sanitize_cell_value(item['status']),
                    sanitize_cell_value(item['assignedTo']),
                    item['dueDate'],
                    item['completedAt'],
                    item['durationHours'],
                    sanitize_cell_value(item['skippedReason'])
                ]

        return headers, row_generator(), "BaoCao_HieuSuatBaoTri_SLA"

    @classmethod
    def _stream_spare_parts(cls, tenant, filters: dict):
        headers = [
            "Mã Phụ Tùng",
            "Tên Phụ Tùng",
            "Số Lượng Tồn Kho",
            "Đơn Giá Bình Quân (VNĐ)",
            "Tổng Giá Trị Tồn (VNĐ)",
            "Trạng Thái Tồn Kho"
        ]

        data = SparePartsValuationEngine.get_spare_parts_data(
            tenant=tenant,
            date_from=parse_date_safe(filters.get('dateFrom')),
            date_to=parse_date_safe(filters.get('dateTo')),
            search=filters.get('search')
        )

        def row_generator():
            for p in data['parts']:
                status = "CẢNH BÁO XUẤT ÂM" if p['isNegative'] else "Bình thường"
                yield [
                    sanitize_cell_value(p['partNumber']),
                    sanitize_cell_value(p['name']),
                    p['quantityInStock'],
                    int(p['unitCost']),
                    int(p['totalValue']),
                    sanitize_cell_value(status)
                ]

        return headers, row_generator(), "BaoCao_PhuTung_TieuHaoKho"

    @classmethod
    def _stream_cost_summary(cls, tenant, filters: dict):
        headers = [
            "Trung Tâm Chi Phí / Phân Xưởng",
            "Chi Phí Vật Tư Thực Tế (VNĐ)",
            "Chi Phí Giờ Công (VNĐ)",
            "Tổng Chi Phí Thực Tế (VNĐ)"
        ]

        data = CostSummaryEngine.get_cost_summary_data(
            tenant=tenant,
            date_from=parse_date_safe(filters.get('dateFrom')),
            date_to=parse_date_safe(filters.get('dateTo')),
            cost_center=filters.get('costCenter'),
            include_capex=filters.get('includeCapex', False)
        )

        def row_generator():
            for r in data['costCenters']:
                yield [
                    sanitize_cell_value(r['costCenter']),
                    int(r['materialCost']),
                    int(r['laborCost']),
                    int(r['totalCost'])
                ]

        return headers, row_generator(), "BaoCao_TongHopChiPhi_BaoTri"

    @classmethod
    def _export_xlsx(cls, headers: List[str], rows, file_path: str, title: str):
        """
        Rule 9 & 10.2: Openpyxl write_only streaming mode.
        Low RAM overhead (<= 200MB) for 50,000+ rows.
        """
        from openpyxl import Workbook
        wb = Workbook(write_only=True)
        ws = wb.create_sheet(title="ReportData")

        # Write header
        ws.append([sanitize_cell_value(h) for h in headers])

        # Write sanitized rows
        for row in rows:
            ws.append([sanitize_cell_value(c) for c in row])

        wb.save(file_path)

    @classmethod
    def _export_csv(cls, headers: List[str], rows, file_path: str):
        with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([sanitize_cell_value(h) for h in headers])
            for row in rows:
                writer.writerow([sanitize_cell_value(c) for c in row])

    @classmethod
    def _export_pdf(cls, headers: List[str], rows, file_path: str, title: str):
        """
        ReportLab PDF generation with auto-wrapping Paragraph cells,
        proportional column widths, and TrueType Unicode font support
        to completely eliminate text overlapping / clipping.
        """
        import html
        import os
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # 1. Register TrueType Unicode font for crisp Vietnamese rendering
        font_name = 'Helvetica'
        font_bold = 'Helvetica-Bold'
        font_candidates = [
            ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf'),
            ('C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/segoeuib.ttf'),
            ('C:/Windows/Fonts/tahoma.ttf', 'C:/Windows/Fonts/tahomabd.ttf'),
        ]
        for regular, bold in font_candidates:
            if os.path.exists(regular) and os.path.exists(bold):
                try:
                    pdfmetrics.registerFont(TTFont('AppUnicode', regular))
                    pdfmetrics.registerFont(TTFont('AppUnicode-Bold', bold))
                    font_name = 'AppUnicode'
                    font_bold = 'AppUnicode-Bold'
                    break
                except Exception:
                    pass

        # 2. Page layout setup (A4 Landscape = 841.89 x 595.28 pt)
        page_width, page_height = landscape(A4)
        margin = 15
        avail_width = page_width - (margin * 2)  # ~811.89 pt

        doc = SimpleDocTemplate(
            file_path,
            pagesize=landscape(A4),
            rightMargin=margin,
            leftMargin=margin,
            topMargin=margin,
            bottomMargin=margin
        )

        elements = []

        # 3. Titles
        title_style = ParagraphStyle(
            'ReportTitle',
            fontName=font_bold,
            fontSize=13,
            leading=16,
            textColor=colors.HexColor('#0f172a'),
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            fontName=font_name,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=10
        )

        clean_title = title.replace('_', ' ')
        elements.append(Paragraph(f"<b>BÁO CÁO DOANH NGHIỆP — {html.escape(clean_title).upper()}</b>", title_style))
        elements.append(Paragraph(f"Ngày xuất: {timezone.now().strftime('%d/%m/%Y %H:%M:%S')} (UTC) — Hệ thống Quản trị Tài sản Doanh nghiệp EAM Enterprise", subtitle_style))

        # 4. Smart proportional column widths based on content type
        col_count = len(headers)
        weights = []
        for h in headers:
            hl = h.lower()
            if any(k in hl for k in ['tiêu đề', 'tên', 'title', 'name', 'diễn giải', 'mô tả']):
                weights.append(2.8)
            elif any(k in hl for k in ['tài sản', 'kỹ thuật viên', 'phân xưởng', 'phụ tùng', 'vị trí', 'location', 'asset', 'technician']):
                weights.append(2.0)
            elif any(k in hl for k in ['kiến nghị', 'lý do', 'ghi chú', 'skipped']):
                weights.append(1.8)
            elif any(k in hl for k in ['loại', 'trạng thái', 'ưu tiên', 'status', 'category', 'type', 'priority']):
                weights.append(1.2)
            elif any(k in hl for k in ['mã', 'serial', 'code', 'id']):
                weights.append(1.2)
            elif any(k in hl for k in ['ngày', 'hạn', 'thời điểm', 'kỳ', 'date', 'time']):
                weights.append(1.2)
            elif any(k in hl for k in ['giá', 'chi phí', 'tiền', 'khấu hao', 'opex', 'capex', 'tồn kho', 'số lượng', 'cost', 'value']):
                weights.append(1.3)
            elif any(k in hl for k in ['rrr', 'giờ', 'tỷ lệ', '%', 'duration', 'hours']):
                weights.append(0.8)
            else:
                weights.append(1.2)
        total_w = sum(weights)
        col_widths = [(w / total_w) * avail_width for w in weights]

        # 5. Font sizing and padding scaled by column density
        if col_count > 12:
            th_font_size, th_leading = 6.5, 8.0
            td_font_size, td_leading = 6.0, 7.5
            pad_h, pad_v = 2, 3
        elif col_count > 8:
            th_font_size, th_leading = 7.5, 9.0
            td_font_size, td_leading = 7.0, 8.5
            pad_h, pad_v = 3, 4
        else:
            th_font_size, th_leading = 8.5, 10.5
            td_font_size, td_leading = 8.0, 9.5
            pad_h, pad_v = 4, 5

        th_style = ParagraphStyle(
            'TH',
            fontName=font_bold,
            fontSize=th_font_size,
            leading=th_leading,
            textColor=colors.whitesmoke,
            alignment=1,  # Center
            wordWrap='CJK'
        )
        td_style = ParagraphStyle(
            'TD',
            fontName=font_name,
            fontSize=td_font_size,
            leading=td_leading,
            textColor=colors.HexColor('#1e293b'),
            alignment=0,  # Left
            wordWrap='CJK'
        )

        # 6. Build table data wrapping ALL cells in Paragraph to guarantee auto-wrapping
        table_data = []
        table_data.append([Paragraph(html.escape(str(sanitize_cell_value(h))), th_style) for h in headers])

        count = 0
        for r in rows:
            table_data.append([
                Paragraph(html.escape(str(sanitize_cell_value(c))), td_style) for c in r
            ])
            count += 1
            if count >= 1000:
                break

        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), pad_v),
            ('TOPPADDING', (0, 0), (-1, -1), pad_v),
            ('LEFTPADDING', (0, 0), (-1, -1), pad_h),
            ('RIGHTPADDING', (0, 0), (-1, -1), pad_h),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f8fafc'), colors.white]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ]))

        elements.append(t)
        doc.build(elements)
