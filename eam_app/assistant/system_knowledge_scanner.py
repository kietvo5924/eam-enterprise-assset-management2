"""
System Knowledge Scanner & Indexer for EAM Portal.
Scans source code templates, navigation structures, and portal capabilities
to dynamically generate and vectorize global system software guides into PGVector and Curated QA.
"""

import os
import re
import logging
from typing import Dict, Any, List
from django.db import connection, transaction
from algorithms.rag_chatbot.vector_engine import embed_text
from assistant.models import TechnicalDocument, DocumentChunk, CuratedQAKnowledge

logger = logging.getLogger(__name__)

# Complete system metadata for all portal modules mapped directly to source code templates
PORTAL_MODULES_METADATA = [
    {
        "id": "portal_dashboard",
        "title": "Trang Tổng Quan (Dashboard & Floorplan)",
        "template": "dashboard.html",
        "route_url": "/portal/",
        "permission": "Mọi người dùng đã đăng nhập",
        "triggers": [
            "trang tổng quan có gì",
            "tổng quan có gì",
            "tổng quan",
            "dashboard có gì",
            "màn hình dashboard có gì",
            "hướng dẫn sử dụng trang tổng quan",
            "chức năng trang tổng quan",
            "sơ đồ mặt bằng có gì",
            "sơ đồ mặt bằng xưởng floorplan",
            "floorplan có gì"
        ],
        "summary": "Trang chỉ huy trung tâm hiển thị chỉ số KPI thời gian thực và sơ đồ mặt bằng xưởng 2D tương tác.",
        "features": [
            "Thẻ thống kê KPI thời gian thực: Tổng tài sản, Máy đang hoạt động, Máy dừng sự cố, Phiếu bảo trì chờ xử lý, Cảnh báo vật tư dưới mức an toàn.",
            "Sơ đồ mặt bằng 2D Floorplan Canvas: Định vị tọa độ tài sản trực quan trong phân xưởng, ghim màu theo trạng thái (Xanh: Bình thường, Đỏ: Sự cố, Vàng: Bảo trì).",
            "Biểu đồ phân tích hiệu suất thiết bị: OEE, tỷ lệ hoàn thành bảo dưỡng đúng hạn, thời gian dừng máy trung bình.",
            "Bảng danh sách công việc khẩn cấp: Theo dõi các phiếu bảo trì phát sinh cần xử lý ngay lập tức."
        ],
        "actions": [
            "Nút 'Bộ lọc thời gian': Lọc chỉ số theo Ngày, Tuần, Tháng, Quý.",
            "Tương tác trên Sơ đồ mặt bằng: Nhấp vào máy trên sơ đồ 2D để xem nhanh thông tin thiết bị, mở chi tiết hoặc chuyển tới phiếu bảo trì.",
            "Nút 'Làm mới dữ liệu': Cập nhật tức thời số liệu đo lường và trạng thái vận hành."
        ]
    },
    {
        "id": "portal_asset_registry",
        "title": "Trang Cây Tài Sản (Asset Registry & Hierarchy)",
        "template": "asset_registry.html",
        "route_url": "/portal/assets/",
        "permission": "asset:read (Xem), asset:write / asset:create (Thêm/Sửa)",
        "triggers": [
            "trang cây tài sản có gì",
            "cây tài sản có gì",
            "cây tài sản",
            "trang tài sản có gì",
            "tài sản có gì",
            "hướng dẫn cây tài sản",
            "hướng dẫn sử dụng cây tài sản",
            "chức năng cây tài sản",
            "cách tra cứu máy móc trên cây tài sản",
            "quét mã qr tài sản"
        ],
        "summary": "Quản lý toàn bộ cấu trúc cây phân cấp tài sản, thiết bị, dây chuyền máy móc đa tầng trong toàn bộ nhà máy.",
        "features": [
            "Cây phân cấp thiết bị đa tầng (Tree View): Cấu trúc hình cây từ Đơn vị -> Khu vực/Phân xưởng -> Dây chuyền sản xuất -> Cụm máy -> Chi tiết bộ phận.",
            "Bảng chi tiết thông tin tài sản: Mã tài sản, Tên máy móc, Model kỹ thuật, Số serial, Năm sản xuất, Nhà sản xuất, Hạn bảo hành, Đơn vị quản lý.",
            "Hệ thống lọc & tìm kiếm: Tìm kiếm theo mã hoặc tên tài sản, lọc theo trạng thái vận hành (Đang hoạt động - OPERATIONAL, Bảo trì - MAINTENANCE, Hỏng hóc - BROKEN, Thanh lý - DECOMMISSIONED).",
            "Tab Thông số kỹ thuật (Parameters): Quản lý các thuộc tính vận hành như công suất, điện áp, áp suất định mức.",
            "Tab Phụ tùng liên kết (Spare Parts / BOM): Danh sách linh kiện, vòng bi, phớt dầu tương thích với máy.",
            "Tab Lịch sử bảo trì (Maintenance History): Danh sách tất cả phiếu bảo trì (Work Orders) đã thực hiện cho thiết bị.",
            "Tab Tài liệu kỹ thuật: Lưu trữ bản vẽ nguyên lý, sổ tay hướng dẫn vận hành OEM và sơ đồ mạch."
        ],
        "actions": [
            "Nút '+ Thêm tài sản mới': Mở modal tạo mới thiết bị máy móc vào đúng vị trí trên cây phân cấp.",
            "Nút 'Nhập (Import)': Tải lên danh sách tài sản hàng loạt từ file Excel/CSV.",
            "Nút 'Xuất/In (Export/Print)': Xuất báo cáo tài sản ra file Excel hoặc in ấn tem nhãn.",
            "Nút 'Quét mã QR Code': Kích hoạt camera quét tem mã QR gắn trên máy để tra cứu nhanh hồ sơ thiết bị tại hiện trường.",
            "Nút 'Tạo phiếu WO': Chuyển nhanh sang màn hình lập phiếu bảo trì cho thiết bị đang chọn.",
            "Nút 'Chỉnh sửa tài sản': Cập nhật thông số kỹ thuật, vị trí lắp đặt và trạng thái máy."
        ]
    },
    {
        "id": "portal_work_orders",
        "title": "Trang Phiếu Bảo Trì (Work Orders & Maintenance)",
        "template": "work_orders.html",
        "route_url": "/portal/work-orders/",
        "permission": "work_order:read (Xem), work_order:create (Tạo), work_order:execute (Thực hiện), work_order:approve (Nghiệm thu)",
        "triggers": [
            "trang phiếu bảo trì có gì",
            "phiếu bảo trì có gì",
            "phiếu bảo trì",
            "trang phiếu sửa chữa có gì",
            "phiếu sửa chữa có gì",
            "phiếu wo có gì",
            "hướng dẫn sử dụng phiếu bảo trì",
            "quy trình phiếu bảo trì",
            "6 trạng thái phiếu bảo trì",
            "cách tạo phiếu bảo trì",
            "nút giao việc ở đâu"
        ],
        "summary": "Quản lý toàn diện vòng đời phiếu bảo trì sửa chữa với 6 trạng thái chuẩn CMMS và các thuật toán điều phối thông minh.",
        "features": [
            "Quy trình vòng đời 6 trạng thái chuẩn: CREATED (Mới tạo) -> ASSIGNED (Đã giao việc) -> IN_PROGRESS (Đang sửa chữa) -> ON_HOLD (Tạm dừng/Chờ vật tư) -> COMPLETED (Đã hoàn thành) -> CANCELLED (Đã hủy).",
            "Bảng danh sách phiếu bảo trì: Phân loại theo mức độ ưu tiên (Khẩn cấp - CRITICAL, Cao - HIGH, Trung bình - MEDIUM, Thấp - LOW).",
            "Bộ lọc đa chiều: Lọc theo trạng thái, nhóm thợ phụ trách, loại bảo trì (Sự cố Corrective vs Định kỳ PM), khoảng thời gian.",
            "Modal chi tiết phiếu WO: Xem mô tả sự cố, tài sản liên quan, kỹ thuật viên phụ trách, nhật ký thao tác và danh sách vật tư đã xuất dùng."
        ],
        "actions": [
            "Nút '+ Tạo phiếu bảo trì': Mở modal lập phiếu sửa chữa mới, chọn thiết bị, mức độ ưu tiên và mô tả sự cố.",
            "Nút 'Điều phối tức thời 1-1' (Hungarian Algorithm): Ghép cặp tối ưu 1 thợ - 1 việc cho các sự cố khẩn cấp bằng giải thuật Kuhn-Munkres.",
            "Nút 'Lập lịch cả ca nhiều việc' (Genetic Algorithm): Phân bổ tối ưu danh mục công việc cho ca trực 8 tiếng bằng giải thuật Di truyền GA.",
            "Nút 'Tối ưu lộ trình di chuyển' (TSP Routing): Sắp xếp thứ tự các điểm dừng sửa chữa tối ưu theo sơ đồ mặt bằng.",
            "Nút 'Giao việc (Assign)': Phân công kỹ thuật viên hoặc đội thợ tiếp nhận phiếu.",
            "Nút 'Bắt đầu sửa chữa (Start)': Chuyển trạng thái sang Đang sửa chữa (IN_PROGRESS) và ghi nhận thời gian bắt đầu.",
            "Nút 'Ghi nhận đo kiểm (Inspection)': Nhập thông số nhiệt độ, rung chấn và ảnh hiện trường.",
            "Nút 'Xuất kho vật tư': Đăng ký linh kiện phụ tùng thay thế và tự động trừ kho.",
            "Nút 'Nghiệm thu & Hoàn thành (Complete)': Kỹ sư trưởng phê duyệt kết quả sửa chữa, chuyển trạng thái COMPLETED."
        ]
    },
    {
        "id": "portal_workforce_tools",
        "title": "Trang Nhân Lực & Quản Lý Công Cụ (Workforce & Tools)",
        "template": "workforce_tools.html",
        "route_url": "/portal/workforce-tools/",
        "permission": "workforce:read, work_order:read, user:read",
        "triggers": [
            "trang nhân lực và công cụ có gì",
            "nhân lực và công cụ có gì",
            "nhân lực & công cụ có gì",
            "trang nhân lực có gì",
            "nhân lực có gì",
            "công cụ có gì",
            "quản lý ca trực kỹ thuật viên",
            "chứng chỉ an toàn",
            "hiệu chuẩn công cụ dụng cụ"
        ],
        "summary": "Quản trị đội ngũ kỹ thuật viên xưởng, phân ca trực, chứng chỉ an toàn lao động và quản lý hiệu chuẩn công cụ đo kiểm.",
        "features": [
            "Quản lý kỹ thuật viên: Hồ sơ tay nghề, chuyên môn (Cơ khí, Thủy lực, Điện - Tự động hóa), bậc thợ và trạng thái sẵn sàng.",
            "Bảng xếp ca trực (Shift Scheduling): Lịch trực theo Ca 1 (Sáng), Ca 2 (Chiều), Ca 3 (Đêm) và theo dõi ngày nghỉ.",
            "Hồ sơ chứng chỉ an toàn (Certifications): Quản lý chứng chỉ an toàn điện cao thế, làm việc trên cao, an toàn áp lực, cảnh báo sắp hết hạn.",
            "Danh mục công cụ chuyên dùng (Tools Management): Quản lý đồng hồ đo vạn năng, máy đo rung chấn, súng đo nhiệt hồng ngoại, cờ lê lực.",
            "Lịch hiệu chuẩn định kỳ (Calibration Tracking): Theo dõi hạn kiểm định và cảnh báo thiết bị quá hạn hiệu chuẩn."
        ],
        "actions": [
            "Nút 'Phân ca làm việc': Xếp ca trực hàng tuần cho đội ngũ kỹ thuật viên.",
            "Nút '+ Thêm công cụ mới': Nhập mới máy đo kiểm, mã định danh và chu kỳ kiểm định.",
            "Nút 'Ghi nhận hiệu chuẩn': Cập nhật ngày kiểm định mới nhất và tải lên biên bản hiệu chuẩn."
        ]
    },
    {
        "id": "portal_pm_plans",
        "title": "Trang Kế Hoạch Bảo Trì Định Kỳ (PM Plans)",
        "template": "pm_plans.html",
        "route_url": "/portal/pm-plans/",
        "permission": "pm_plan:read (Xem), pm_plan:write (Thêm/Sửa/Lập lịch)",
        "triggers": [
            "trang kế hoạch pm có gì",
            "kế hoạch pm có gì",
            "kế hoạch pm",
            "bảo trì định kỳ có gì",
            "bảo trì định kỳ",
            "hướng dẫn tạo kế hoạch pm",
            "lập lịch bảo trì theo giờ chạy máy",
            "tự động sinh phiếu wo định kỳ"
        ],
        "summary": "Lập kế hoạch bảo trì phòng ngừa định kỳ theo thời gian hoặc theo chỉ số giờ chạy máy để chủ động ngăn ngừa sự cố.",
        "features": [
            "Lập lịch theo chu kỳ thời gian (Calendar-based): Lặp lại định kỳ theo ngày, tuần, tháng, quý, năm.",
            "Lập lịch theo chỉ số vận hành (Meter/Runtime-based): Kích hoạt khi đồng hồ đo giờ chạy máy đạt ngưỡng (ví dụ: mỗi 500 giờ chạy máy).",
            "Danh mục công việc kiểm tra (Checklist Tasks): Quy định chi tiết các bước cần làm (tra dầu mỡ bôi trơn, siết ốc, vệ sinh lưới lọc, căng đai).",
            "Cơ chế tự động sinh phiếu (Auto WorkOrder Generation): Tự động phát hành phiếu bảo trì khi đến hạn bảo dưỡng."
        ],
        "actions": [
            "Nút '+ Tạo kế hoạch PM mới': Định nghĩa kế hoạch bảo trì mới cho cụm máy hoặc dây chuyền.",
            "Nút 'Chạy kích hoạt thủ công': Kích hoạt sinh phiếu bảo trì ngay lập tức mà không cần chờ đến lịch.",
            "Nút 'Cập nhật chỉ số đồng hồ (Log Meter)': Ghi nhận số giờ chạy máy thực tế từ đồng hồ đo."
        ]
    },
    {
        "id": "portal_inventory",
        "title": "Trang Kho Vật Tư & Phụ Tùng (Inventory Management)",
        "template": "inventory.html",
        "route_url": "/portal/inventory/",
        "permission": "inventory:read (Xem), inventory:write (Nhập/Xuất/Điều chỉnh kho)",
        "triggers": [
            "trang kho vật tư có gì",
            "kho vật tư có gì",
            "kho vật tư",
            "trang kho phụ tùng có gì",
            "kho phụ tùng có gì",
            "kho phụ tùng",
            "vật tư phụ tùng có gì",
            "hướng dẫn sử dụng kho vật tư",
            "cảnh báo tồn kho tối thiểu min stock",
            "cách nhập xuất vật tư phụ tùng"
        ],
        "summary": "Quản lý tồn kho linh kiện, phụ tùng thay thế, vật tư tiêu hao, vị trí kệ ngăn và cảnh báo dưới ngưỡng an toàn.",
        "features": [
            "Danh mục phụ tùng & vật tư: Mã linh kiện, tên phụ tùng, đơn vị tính, đơn giá, nhà cung cấp, thông số kỹ thuật.",
            "Số lượng tồn kho thực tế: Tồn kho khả dụng, tồn kho đã giữ chỗ cho phiếu bảo trì đang mở.",
            "Cảnh báo ngưỡng an toàn (Min-Stock Threshold): Đánh dấu đỏ cảnh báo tự động khi số lượng tồn kho giảm xuống dưới mức tối thiểu.",
            "Vị trí kho bãi chi tiết: Định vị linh kiện theo Nhà kho -> Dãy kệ -> Tầng -> Ngăn chứa.",
            "Lịch sử phiếu nhập / xuất kho: Truy vết chi tiết từng lần xuất vật tư gắn liền với mã phiếu bảo trì tương ứng."
        ],
        "actions": [
            "Nút '+ Nhập kho mới': Tạo phiếu nhập kho vật tư từ nhà cung cấp.",
            "Nút 'Xuất kho cho phiếu WO': Trừ tồn kho vật tư phục vụ công tác sửa chữa hiện trường.",
            "Nút 'Kiểm kê điều chỉnh kho': Cân chỉnh số lượng tồn kho sổ sách với kiểm kê thực tế.",
            "Nút 'Xuất danh sách Excel': Tải báo cáo tồn kho và danh sách vật tư cần đặt mua bổ sung."
        ]
    },
    {
        "id": "portal_reports",
        "title": "Trang Báo Cáo & Phân Tích (Reports & Analytics)",
        "template": "reports.html",
        "route_url": "/portal/reports/",
        "permission": "reports:read",
        "triggers": [
            "trang báo cáo có gì",
            "báo cáo có gì",
            "báo cáo",
            "chức năng báo cáo",
            "báo cáo kpi có gì",
            "báo cáo oee mtbf mttr",
            "xuất báo cáo excel pdf"
        ],
        "summary": "Trung tâm phân tích hiệu suất thiết bị toàn diện, chỉ số độ tin cậy bảo trì và chi phí vận hành nhà máy.",
        "features": [
            "Chỉ số OEE (Overall Equipment Effectiveness): Hiệu suất thiết bị tổng thể (Sẵn sàng - Hiệu suất - Chất lượng).",
            "Chỉ số MTBF (Mean Time Between Failures): Thời gian trung bình giữa các lần hư hỏng sự cố.",
            "Chỉ số MTTR (Mean Time To Repair): Thời gian trung bình để hoàn thành một ca sửa chữa.",
            "Phân tích chi phí bảo trì: Tỷ trọng chi phí nhân công, chi phí linh kiện phụ tùng và tổng thiệt hại do dừng máy (Downtime).",
            "Báo cáo tỷ lệ hoàn thành bảo dưỡng định kỳ (PM Compliance Rate)."
        ],
        "actions": [
            "Nút 'Lọc khoảng thời gian': Xem báo cáo theo Tháng, Quý, Năm hoặc khoảng ngày tùy chọn.",
            "Nút 'Xuất Excel': Tải toàn bộ dữ liệu phân tích ra bảng tính Excel phục vụ làm báo cáo quản trị.",
            "Nút 'In / Xuất PDF': Xuất báo cáo trang bìa đồ thị chuyên nghiệp."
        ]
    },
    {
        "id": "portal_cost_forecasting",
        "title": "Trang Dự Báo Chi Phí & Vòng Đời LCC (Cost Forecasting)",
        "template": "cost_forecasting.html",
        "route_url": "/portal/cost-forecasting/",
        "permission": "cost_forecast:read, reports:read",
        "triggers": [
            "trang dự báo chi phí có gì",
            "dự báo chi phí có gì",
            "dự báo chi phí",
            "vòng đời tài sản lcc",
            "vòng đời lcc có gì",
            "dự báo chi phí bảo trì tương lai",
            "tối ưu thời điểm thanh lý thay mới máy"
        ],
        "summary": "Ứng dụng mô hình kinh tế kỹ thuật dự báo chi phí bảo trì tương lai và phân tích chi phí vòng đời thiết bị (LCC).",
        "features": [
            "Mô hình chi phí vòng đời LCC (Life Cycle Costing): Tổng hợp chi phí mua sắm ban đầu (CAPEX), chi phí vận hành bảo dưỡng (OPEX), và giá trị thanh lý.",
            "Dự báo xu hướng chi phí bảo dưỡng trong 12 - 36 tháng tới dựa trên độ tuổi máy móc và tần suất hỏng hóc.",
            "Điểm kinh tế tối ưu thay thế thiết bị (Optimal Replacement Point): Xác định thời điểm chi phí sửa chữa vượt quá hiệu quả đầu tư máy mới."
        ],
        "actions": [
            "Nút 'Chạy mô hình dự báo': Áp dụng thuật toán dự toán chi phí bảo trì cho năm tài chính tiếp theo.",
            "Nút 'So sánh phương án LCC': Đặt lên bàn cân phương án tiếp tục đại tu sửa chữa so với mua mới."
        ]
    },
    {
        "id": "portal_users",
        "title": "Trang Quản Lý Người Dùng (Users Management)",
        "template": "users.html",
        "route_url": "/portal/users/",
        "permission": "user:read (Xem), user:write (Thêm/Sửa/Khóa tài khoản)",
        "triggers": [
            "trang người dùng có gì",
            "người dùng có gì",
            "người dùng",
            "quản lý người dùng có gì",
            "quản lý người dùng",
            "tạo tài khoản nhân viên",
            "khóa mở khóa người dùng"
        ],
        "summary": "Quản lý danh sách tài khoản nhân sự, kỹ thuật viên, kỹ sư và cán bộ quản lý trong đơn vị.",
        "features": [
            "Danh sách tài khoản: Họ tên, tên đăng nhập, email, số điện thoại, phòng ban và vai trò đảm nhiệm.",
            "Trạng thái tài khoản: Kích hoạt (Active), Tạm khóa (Suspended).",
            "Phân loại theo đơn vị/chi nhánh trong mô hình đa chi nhánh."
        ],
        "actions": [
            "Nút '+ Thêm người dùng mới': Tạo tài khoản đăng nhập cho nhân viên mới và gán vai trò ban đầu.",
            "Nút 'Đặt lại mật khẩu': Cấp lại mật khẩu bảo mật cho nhân viên.",
            "Nút 'Khóa / Mở khóa tài khoản': Tạm dừng quyền truy cập khi nhân sự chuyển công tác."
        ]
    },
    {
        "id": "portal_roles",
        "title": "Trang Phân Quyền & Vai Trò (Roles & RBAC Permissions)",
        "template": "roles.html",
        "route_url": "/portal/roles/",
        "permission": "role:read (Xem), role:write (Tạo/Sửa quyền vai trò)",
        "triggers": [
            "trang phân quyền có gì",
            "phân quyền có gì",
            "phân quyền",
            "quản lý vai trò có gì",
            "vai trò có gì",
            "phân quyền vai trò có gì",
            "hướng dẫn phân quyền rbac",
            "cách tạo vai trò mới",
            "ma trận quyền hạn hệ thống"
        ],
        "summary": "Quản lý hệ thống phân quyền dựa trên vai trò (RBAC) với ma trận quyền hạn chi tiết đến từng thao tác.",
        "features": [
            "Danh sách vai trò: Kỹ sư trưởng (Chief Engineer), Kỹ thuật viên bảo trì (Technician), Thủ kho (Storekeeper), Giám sát sản xuất, Quản trị viên (Admin).",
            "Ma trận quyền hạn phân hệ: Tài sản (asset), Phiếu bảo trì (work_order), Kho vật tư (inventory), Kế hoạch PM (pm_plan), Báo cáo (reports), Tri thức AI (assistant:manage_knowledge), Người dùng (user), Vai trò (role)."
        ],
        "actions": [
            "Nút '+ Tạo vai trò mới': Thiết lập chức danh mới và tích chọn các quyền hạn tương ứng trong ma trận.",
            "Nút 'Chỉnh sửa quyền': Bổ sung hoặc thu hồi quyền hạn của vai trò.",
            "Nút 'Xóa vai trò': Loại bỏ vai trò không còn sử dụng."
        ]
    },
    {
        "id": "portal_asset_categories",
        "title": "Trang Cấu Hình Tài Sản & Vị Trí (Asset Configuration)",
        "template": "asset_categories.html",
        "route_url": "/portal/asset-categories/",
        "permission": "asset_category:read, asset:read",
        "triggers": [
            "trang cấu hình tài sản có gì",
            "cấu hình tài sản có gì",
            "cấu hình tài sản",
            "danh mục tài sản có gì",
            "danh mục loại tài sản",
            "cấu hình vị trí phân xưởng",
            "nhóm thiết bị máy móc"
        ],
        "summary": "Thiết lập cấu hình danh mục phân loại máy móc và sơ đồ vị trí không gian địa lý của các nhà xưởng.",
        "features": [
            "Quản lý Danh mục tài sản: Động cơ điện, Bơm thủy lực, Máy nén khí, Băng tải công nghiệp, Máy CNC, Lò nhiệt luyện.",
            "Quản lý Vị trí vật lý: Danh sách Tòa nhà, Phân xưởng sản xuất, Khu vực phụ trợ, Trạm cấp nguồn điện."
        ],
        "actions": [
            "Nút '+ Thêm danh mục mới': Tạo mới nhóm phân loại máy móc kèm biểu tượng và mã tiền tố.",
            "Nút '+ Thêm vị trí mới': Khởi tạo khu vực mặt bằng mới để liên kết với tài sản trên cây thiết bị."
        ]
    },
    {
        "id": "portal_settings",
        "title": "Trang Cài Đặt Hệ Thống & Đơn Vị (Tenant Settings)",
        "template": "settings.html",
        "route_url": "/portal/settings/",
        "permission": "tenant:read (Xem), tenant:update (Cập nhật cấu hình)",
        "triggers": [
            "trang cài đặt có gì",
            "cài đặt có gì",
            "cài đặt",
            "cài đặt đơn vị có gì",
            "cài đặt hệ thống có gì",
            "cài đặt đơn vị",
            "thay đổi logo thương hiệu",
            "đổi bảng màu chủ đề giao diện",
            "cấu hình múi giờ và tiền tệ"
        ],
        "summary": "Cài đặt tham số vận hành của đơn vị/tenant: Nhận diện thương hiệu, giao diện, múi giờ và cấu hình thông báo.",
        "features": [
            "Thông tin doanh nghiệp: Tên đơn vị, Mã định danh tenant, Địa chỉ nhà máy, Mã số thuế.",
            "Nhận diện thương hiệu (Branding): Tải lên Logo xưởng, chọn bảng màu giao diện chủ đạo (Cyan, Emerald, Navy, Indigo, Amber).",
            "Cấu hình khu vực: Múi giờ xưởng (Asia/Ho_Chi_Minh), đơn vị tiền tệ mặc định (VND, USD).",
            "Cấu hình thông báo: Bật/tắt thông báo sự cố qua Email hoặc Webhook."
        ],
        "actions": [
            "Nút 'Lưu thay đổi': Áp dụng cấu hình giao diện và thông tin đơn vị ngay tức thì.",
            "Nút 'Tải lên Logo': Chọn tệp ảnh logo thương hiệu từ máy tính để hiển thị trên góc Header."
        ]
    },
    {
        "id": "portal_rag_knowledge",
        "title": "Trang Quản Trị Tri Thức AI (AI Knowledge Hub)",
        "template": "rag_knowledge.html",
        "route_url": "/admin/rag-knowledge/",
        "permission": "assistant:manage_knowledge (hoặc tenant:update, system:admin)",
        "triggers": [
            "trang tri thức ai có gì",
            "tri thức ai có gì",
            "tri thức ai",
            "trợ lý ai có gì",
            "trợ lý ai",
            "hướng dẫn trang tri thức ai",
            "tri thức vàng có gì",
            "tri thức vàng curated qa",
            "hàng đợi thẩm định có gì",
            "hàng đợi thẩm định tacit queue",
            "thư viện tài liệu kỹ thuật"
        ],
        "summary": "Trung tâm quản trị tri thức kỹ thuật cho Trợ lý AI: Thư viện tài liệu OEM, Hàng đợi thẩm duyệt mẹo bảo trì và Tri thức Vàng chuẩn hóa.",
        "features": [
            "Tab 1: Tri thức mẫu (Curated Gold Q&A): Danh sách các cặp Câu hỏi - Câu trả lời kỹ thuật chuẩn hóa đã được Kỹ sư trưởng phê duyệt, vector hóa vào PGVector để phản hồi tức thì với độ chính xác cao.",
            "Tab 2: Hàng đợi thẩm định (Tacit Curation Queue): Thu thập các giải pháp khắc phục sự cố hay từ phiếu bảo trì đã hoàn thành (Work Orders status=COMPLETED) do luồng AI tự động quét nạp định kỳ, chờ Kỹ sư trưởng duyệt nâng cấp thành Tri thức Vàng.",
            "Tab 3: Thư viện tài liệu (Document Library): Lưu trữ và quản lý các cuốn sổ tay vận hành thiết bị OEM, tài liệu hướng dẫn kỹ thuật PDF/Word đã được bóc tách phân đoạn (Parent-Child chunks)."
        ],
        "actions": [
            "Nút '+ Thêm Tri Thức Mới': Nhập thủ công một cặp câu hỏi và câu trả lời kỹ thuật chuẩn mực.",
            "Nút 'Duyệt (Approve)': Phê duyệt một mẹo sửa chữa từ Hàng đợi thẩm định thành Tri thức Vàng.",
            "Nút 'Từ chối (Reject)': Loại bỏ một đề xuất không đạt chuẩn chất lượng khỏi hàng đợi.",
            "Nút 'Tải lên tài liệu mới': Đăng tải file tài liệu kỹ thuật PDF để phân đoạn và vector hóa."
        ]
    },
    {
        "id": "portal_audit_logs",
        "title": "Trang Nhật Ký Hệ Thống (Audit Logs)",
        "template": "audit_logs.html",
        "route_url": "/portal/audit-logs/",
        "permission": "audit_logs:read",
        "triggers": [
            "trang nhật ký hệ thống có gì",
            "nhật ký hệ thống có gì",
            "nhật ký hệ thống",
            "audit logs có gì",
            "audit logs",
            "lịch sử kiểm toán truy vết",
            "theo dõi ai đã sửa dữ liệu"
        ],
        "summary": "Ghi nhận toàn bộ nhật ký truy vết bảo mật, kiểm toán hoạt động thao tác của người dùng trên toàn hệ thống.",
        "features": [
            "Dòng thời gian sự kiện: Thời điểm thao tác (Timestamp), Tài khoản thực hiện (Username), Địa chỉ IP.",
            "Hành động nghiệp vụ: Đăng nhập (LOGIN), Thêm mới (CREATE), Sửa đổi (UPDATE), Xóa bỏ (DELETE), Đổi trạng thái phiếu bảo trì.",
            "Chi tiết thay đổi (Diff Change): Xem dữ liệu trước và sau khi chỉnh sửa để đối chiếu."
        ],
        "actions": [
            "Nút 'Lọc theo hành động': Lọc theo loại thao tác cụ thể hoặc tài khoản nhân viên.",
            "Nút 'Xuất nhật ký': Tải file nhật ký kiểm toán phục vụ thanh tra an ninh thông tin."
        ]
    },
    {
        "id": "portal_tenants",
        "title": "Trang Quản Lý Đơn Vị (Tenants Management)",
        "template": "tenants.html",
        "route_url": "/portal/tenants/",
        "permission": "Chỉ dành cho Quản trị viên cấp cao (Superadmin hệ thống thuộc tenant SYSTEM)",
        "triggers": [
            "trang đơn vị có gì",
            "đơn vị có gì",
            "đơn vị",
            "trang tenant có gì",
            "tenant có gì",
            "quản lý tenant có gì",
            "quản trị đa đơn vị doanh nghiệp"
        ],
        "summary": "Quản trị đa đơn vị doanh nghiệp trong mô hình SaaS/Multi-tenant dành riêng cho Superadmin.",
        "features": [
            "Danh sách các đơn vị/công ty thành viên trong tập đoàn.",
            "Hạn mức tài nguyên (Quota): Số lượng máy móc tối đa, dung lượng tài liệu, số tài khoản người dùng cho phép.",
            "Trạng thái kích hoạt và gói dịch vụ của từng đơn vị."
        ],
        "actions": [
            "Nút '+ Khởi tạo đơn vị mới': Đăng ký một công ty/nhà máy mới vào hệ thống EAM.",
            "Nút 'Cấu hình hạn mức': Điều chỉnh dung lượng và giới hạn tài nguyên của đơn vị."
        ]
    }
]


def generate_module_guide_markdown(mod: Dict[str, Any]) -> str:
    """Formats module metadata into a beautiful, structured Markdown guide section."""
    lines = [
        f"## {mod['title'].upper()}",
        f"- **Đường dẫn (URL)**: `{mod['route_url']}` (Template: `{mod['template']}`)",
        f"- **Quyền hạn truy cập**: {mod['permission']}",
        f"- **Mục đích & Tổng quan**: {mod['summary']}",
        "",
        "### 📋 Các Chức Năng & Khu Vực Hiển Thị Chính:"
    ]
    for feat in mod['features']:
        lines.append(f"  • {feat}")
    
    lines.append("")
    lines.append("### ⚙️ Các Nút Bấm & Thao Tác Nghiệp Vụ Trên Trang:")
    for act in mod['actions']:
        lines.append(f"  • {act}")
        
    return "\n".join(lines)


def scan_and_index_system_knowledge() -> Dict[str, Any]:
    """
    Executes automated codebase scan of portal modules, generates clean Parent-Child chunks,
    vectorizes them into PGVector, and registers corresponding Curated QA entries.
    All system knowledge chunks are stored globally (tenant_id=NULL, is_system_guide=TRUE).
    """
    logger.info("Scanning portal codebase and indexing dynamic system knowledge...")
    
    # 1. Master System Guide Technical Document
    doc, _ = TechnicalDocument.objects.update_or_create(
        title="Sổ Tay Tính Năng & Hướng Dẫn Sử Dụng EAM Portal",
        tenant_id=None,
        defaults={
            "category": "SYSTEM_SOFTWARE_GUIDE",
            "file_path": "system://portal_guide.pdf",
            "file_size_bytes": 1024 * 1024,
            "is_system_guide": True,
            "is_active": True
        }
    )

    indexed_count = 0
    curated_count = 0

    with transaction.atomic():
        # Clean existing system guide chunks for doc
        DocumentChunk.all_objects.filter(document=doc).delete()

        # Iterate over all portal modules
        for page_idx, mod in enumerate(PORTAL_MODULES_METADATA, start=1):
            guide_md = generate_module_guide_markdown(mod)
            section_title = mod['title']

            # Create Child Chunks directly from clean trigger queries
            for trig in mod['triggers']:
                clean_trig = trig.strip().lower()
                child_vec = embed_text(clean_trig)

                DocumentChunk.objects.create(
                    document=doc,
                    tenant_id=None,
                    is_system_guide=True,
                    source_type='SYSTEM_GUIDE',
                    section_title=section_title,
                    content=clean_trig,
                    parent_content=guide_md,
                    embedding=child_vec,
                    page_number=page_idx,
                    is_active=True
                )
                indexed_count += 1

            # Register/update Curated Gold Q&A for this page
            primary_question = mod['triggers'][0]
            CuratedQAKnowledge.all_objects.filter(
                question_pattern__iexact=primary_question
            ).delete()

            qa = CuratedQAKnowledge.objects.create(
                tenant_id=None,
                is_system_guide=True,
                category='SYSTEM_FEATURE',
                question_pattern=primary_question,
                gold_answer=guide_md,
                applicable_model=None
            )
            curated_count += 1

    logger.info("Successfully indexed %d chunks across %d modules with %d Curated Q&As.", 
                indexed_count, len(PORTAL_MODULES_METADATA), curated_count)
    
    return {
        "success": True,
        "indexed_chunks": indexed_count,
        "modules_scanned": len(PORTAL_MODULES_METADATA),
        "curated_qa_created": curated_count
    }
