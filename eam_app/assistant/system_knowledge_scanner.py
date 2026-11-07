"""
System Knowledge Scanner & Indexer for EAM Portal.
Scans source code templates, navigation structures, and portal capabilities
to dynamically generate and vectorize global system software guides into PGVector and Curated QA.
Provides deep button-level, modal-level, and form-level operational intelligence.
"""

import os
import re
import logging
from typing import Dict, Any, List
from django.db import connection, transaction
from algorithms.rag_chatbot.vector_engine import embed_text, embed_texts
from assistant.models import TechnicalDocument, DocumentChunk, CuratedQAKnowledge

logger = logging.getLogger(__name__)

# Complete system metadata for all portal modules mapped directly to source code templates and action buttons
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
            "floorplan có gì",
            "menu tổng quan ở đâu"
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
        ],
        "action_details": [
            {
                "name": "Bộ Lọc Thời Gian Dashboard",
                "location": "Thanh công cụ trên cùng của màn hình Tổng quan Dashboard (/portal/).",
                "trigger_workflow": "Mở menu thả xuống (Dropdown) để lọc các chỉ số KPI và biểu đồ theo chu kỳ thời gian.",
                "permission": "Mọi người dùng đã đăng nhập (Không yêu cầu quyền đặc biệt)",
                "form_fields": [
                    "Chu kỳ thời gian: Chọn Hôm nay (Ngày), Tuần này, Tháng này, Quý này hoặc Năm nay.",
                    "Khoảng ngày tùy chọn: Nhập ngày bắt đầu và ngày kết thúc để lọc số liệu theo khoảng tùy biến."
                ],
                "notes": "Sau khi chọn khoảng thời gian, toàn bộ các thẻ KPI và biểu đồ OEE sẽ tự động tính toán lại theo mốc đã chọn.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút bộ lọc thời gian",
                    "cách dùng nút bộ lọc thời gian",
                    "làm sao để lọc theo tháng trên dashboard",
                    "nút bộ lọc thời gian ở đâu",
                    "hướng dẫn thao tác lọc thời gian dashboard",
                    "lọc kpi theo tuần bấm ở đâu",
                    "nút lọc thời gian nằm ở đâu"
                ]
            },
            {
                "name": "Làm Mới Dữ Liệu Dashboard",
                "location": "Góc trên bên phải thanh công cụ Dashboard (/portal/), biểu tượng mũi tên xoay vòng (Refresh).",
                "trigger_workflow": "Kích hoạt truy vấn cập nhật tức thời toàn bộ chỉ số KPI, số lượng máy dừng và phiếu bảo trì khẩn cấp mà không cần tải lại toàn bộ trang web.",
                "permission": "Mọi người dùng đã đăng nhập",
                "form_fields": [
                    "Thao tác 1 chạm trực tiếp, không yêu cầu điền biểu mẫu."
                ],
                "notes": "Hữu ích khi theo dõi tiến độ sự cố khẩn cấp trên màn hình điều hành trung tâm xưởng.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút làm mới dữ liệu",
                    "cách dùng nút làm mới dữ liệu",
                    "nút làm mới dữ liệu trên dashboard ở đâu",
                    "nút làm mới dữ liệu trên dashboard nằm ở đâu",
                    "nút làm mới dữ liệu ở đâu",
                    "làm sao cập nhật số liệu dashboard tức thời",
                    "hướng dẫn bấm nút refresh",
                    "nút refresh kpi nằm ở đâu"
                ]
            },
            {
                "name": "Tương Tác Sơ Đồ Mặt Bằng 2D Floorplan",
                "location": "Khu vực trung tâm màn hình Tổng quan Dashboard (/portal/).",
                "trigger_workflow": "Nhấp chuột trực tiếp vào biểu tượng thiết bị trên sơ đồ 2D để mở thẻ popup tóm tắt máy (Quick Popup).",
                "permission": "Mọi người dùng đã đăng nhập",
                "form_fields": [
                    "Xem trạng thái máy: Màu Xanh (Đang hoạt động), Màu Đỏ (Dừng sự cố), Màu Vàng (Đang bảo trì).",
                    "Nút 'Xem chi tiết máy': Chuyển hướng tới hồ sơ thiết bị trên cây tài sản.",
                    "Nút 'Tạo phiếu WO': Mở modal tạo phiếu sửa chữa ngay lập tức cho máy đang chọn."
                ],
                "notes": "Có thể phóng to thu nhỏ (Zoom) hoặc kéo di chuyển (Pan) trên bản đồ mặt bằng xưởng.",
                "action_triggers": [
                    "cách tương tác trên sơ đồ mặt bằng",
                    "bấm vào máy trên floorplan",
                    "sơ đồ mặt bằng bấm vào đâu",
                    "chỉ tôi xem máy trên sơ đồ 2d",
                    "hướng dẫn xem vị trí máy trên sơ đồ",
                    "thao tác trên floorplan thế nào"
                ]
            }
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
            "menu cây tài sản ở đâu"
        ],
        "summary": "Quản lý toàn bộ cấu trúc cây phân cấp tài sản, thiết bị, dây chuyền máy móc đa tầng trong toàn bộ nhà máy.",
        "features": [
            "Cây phân cấp thiết bị đa tầng (Tree View): Cấu trúc hình cây từ Đơn vị -> Khu vực/Phân xưởng -> Dây chuyền sản xuất -> Cụm máy -> Chi tiết bộ phận.",
            "Bảng chi tiết thông tin tài sản: Mã tài sản, Tên máy móc, Model kỹ thuật, Số serial, Năm sản xuất, Nhà sản xuất, Hạn bảo hành, Đơn vị quản lý.",
            "Hệ thống lọc & tìm kiếm: Tìm kiếm theo mã hoặc tên tài sản, lọc theo trạng thái vận hành (OPERATIONAL, MAINTENANCE, BROKEN, DECOMMISSIONED).",
            "Tab Thông số kỹ thuật: Quản lý các thuộc tính vận hành như công suất, điện áp, áp suất định mức.",
            "Tab Phụ tùng liên kết (Spare Parts / BOM): Danh sách linh kiện, vòng bi, phớt dầu tương thích với máy.",
            "Tab Lịch sử bảo trì: Danh sách tất cả phiếu bảo trì (Work Orders) đã thực hiện cho thiết bị.",
            "Tab Tài liệu kỹ thuật: Lưu trữ bản vẽ nguyên lý, sổ tay hướng dẫn vận hành OEM và sơ đồ mạch."
        ],
        "actions": [
            "Nút '+ Thêm tài sản mới': Mở modal tạo mới thiết bị máy móc vào đúng vị trí trên cây phân cấp.",
            "Nút 'Nhập (Import)': Tải lên danh sách tài sản hàng loạt từ file Excel/CSV.",
            "Nút 'Xuất/In (Export/Print)': Xuất báo cáo tài sản ra file Excel hoặc in ấn tem nhãn.",
            "Nút 'Quét mã QR Code': Kích hoạt camera quét tem mã QR gắn trên máy để tra cứu nhanh hồ sơ thiết bị tại hiện trường.",
            "Nút 'Tạo phiếu WO': Chuyển nhanh sang màn hình lập phiếu bảo trì cho thiết bị đang chọn.",
            "Nút 'Chỉnh sửa tài sản': Cập nhật thông số kỹ thuật, vị trí lắp đặt và trạng thái máy."
        ],
        "action_details": [
            {
                "name": "Thêm Tài Sản Mới",
                "location": "Thanh tiêu đề cột Cây Tài Sản bên trái (Left Pane Header) của trang Cây Tài Sản (/portal/assets/), nút biểu tượng dấu cộng '+'.",
                "trigger_workflow": "Mở popup modal 'Thêm Mới Tài Sản' (#asset-modal).",
                "permission": "asset:create hoặc asset:write",
                "form_fields": [
                    "Tên tài sản (asset-name, *bắt buộc): Tên máy móc thiết bị (VD: Máy bơm ly tâm PUMP-01, Máy nén khí trục vít Air-2).",
                    "Mã tài sản / Serial (asset-serial, *bắt buộc): Số seri xuất xưởng của nhà chế tạo hoặc mã quản lý tài sản nội bộ.",
                    "Danh mục tài sản (asset-category, *bắt buộc): Chọn nhóm thiết bị (Động cơ điện, Bơm ly tâm, Máy nén khí, Máy CNC...).",
                    "Model kỹ thuật (asset-model): Mã hiệu model thiết bị từ OEM (VD: PUMP-X100, COMP-500).",
                    "Nhà sản xuất (asset-manufacturer): Hãng chế tạo thiết bị (VD: Grundfos, Siemens, Mitsubishi).",
                    "Ngày mua / Đưa vào sử dụng (asset-purchase-date): Thời điểm mua sắm hoặc nghiệm thu đưa vào dây chuyền.",
                    "Giá trị ban đầu CAPEX (asset-value): Nguyên giá mua sắm tài sản bằng tiền VNĐ.",
                    "Vị trí phân xưởng (asset-location): Chọn khu vực lắp đặt, tầng lầu, phòng kỹ thuật trên cây to-pô xưởng.",
                    "Tỷ lệ chu kỳ tải (asset-duty-cycle): Hệ số vận hành thực tế (từ 0.1 đến 2.0, mặc định 1.0).",
                    "Bắt buộc quét sóng ESP32 BLE Beacon 50m (asset-require-ble-beacon): Checkbox bật/tắt yêu cầu quét sóng Bluetooth beacon khi KTV đến gần máy để điểm danh hiện trường."
                ],
                "notes": "Bấm nút 'Lưu Tài Sản' ở chân modal để lưu vào hệ thống, hoặc bấm nút 'Hủy' để đóng modal.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút thêm tài sản đi",
                    "chỉ tôi sử dụng nút thêm tài sản mới",
                    "chỉ tôi sử dụng nút thêm tài sản",
                    "làm sao để bấm nút thêm tài sản mới",
                    "làm sao để bấm nút thêm tài sản",
                    "cách dùng nút thêm tài sản",
                    "nút thêm tài sản ở đâu",
                    "nút thêm tài sản nằm ở đâu",
                    "hướng dẫn thao tác thêm tài sản",
                    "form thêm tài sản điền gì",
                    "form thêm máy móc điền gì",
                    "quyền bấm nút thêm tài sản",
                    "nút thêm tài sản cần quyền gì",
                    "cách tạo tài sản mới"
                ]
            },
            {
                "name": "Nhập (Import) Excel/CSV Tài Sản",
                "location": "Thanh tiêu đề cột Cây Tài Sản bên trái (Left Pane Header), cạnh nút thêm mới, biểu tượng mũi tên tải lên (ph-upload-simple).",
                "trigger_workflow": "Mở modal 'Nhập Dữ Liệu Tài Sản Hàng Loạt' (#import-modal).",
                "permission": "asset:create hoặc asset:write",
                "form_fields": [
                    "Tải file mẫu (.xlsx): Bấm liên kết tải bảng tính mẫu chuẩn có sẵn cột định dạng.",
                    "Tệp tin đính kèm (*bắt buộc): Chọn file Excel/CSV từ máy tính chứa danh mục máy móc cần nhập.",
                    "Chế độ xử lý trùng mã: Tùy chọn bỏ qua bản ghi trùng hoặc cập nhật đè lên thiết bị đã có."
                ],
                "notes": "Nên tải file mẫu về trước để điền đúng tên cột và mã danh mục quy định.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút nhập excel tài sản",
                    "cách dùng nút import tài sản",
                    "nút import tài sản ở đâu",
                    "nút nhập excel tài sản ở đâu",
                    "làm sao để import danh sách máy móc",
                    "hướng dẫn thao tác nhập excel tài sản",
                    "nhập hàng loạt thiết bị bằng file excel"
                ]
            },
            {
                "name": "Xuất/In (Export/Print) / In Mã QR Tài Sản",
                "location": "Thanh tiêu đề cột Cây Tài Sản bên trái, biểu tượng máy in (ph-printer).",
                "trigger_workflow": "Mở modal 'In Mã QR Hàng Loạt & Xuất Dữ Liệu' (#bulk-filter-modal).",
                "permission": "asset:read",
                "form_fields": [
                    "Lọc theo trạng thái: Chọn in tem cho máy OPERATIONAL, MAINTENANCE, hoặc tất cả.",
                    "Lọc theo danh mục: Chọn nhóm thiết bị cần in ấn tem nhãn.",
                    "Lọc theo vị trí phân xưởng: Chọn tầng xưởng hoặc dây chuyền sản xuất.",
                    "Nút 'In Mã QR': Kích hoạt cửa sổ in tem nhãn có sẵn mã QR, tên máy, mã định danh và danh mục.",
                    "Nút 'Xuất Excel': Kết xuất danh mục toàn bộ tài sản ra tệp bảng tính .xlsx."
                ],
                "notes": "Mã QR in ra được dán trực tiếp lên thân vỏ máy phục vụ việc quét bằng camera tại hiện trường.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút in qr",
                    "cách dùng nút in mã qr",
                    "nút in qr ở đâu",
                    "nút in tem qr nằm chỗ nào trên cây tài sản",
                    "in tem mã qr tài sản dán lên máy móc bấm nút gì",
                    "in tem mã qr tài sản thế nào",
                    "làm sao để in qr code tài sản",
                    "hướng dẫn xuất in tem qr"
                ]
            },
            {
                "name": "Quét Mã QR Code Tra Cứu Máy",
                "location": "Góc trên ứng dụng di động Mobile App hoặc nút quét QR trên giao diện web/thẻ tài sản.",
                "trigger_workflow": "Kích hoạt camera thiết bị để quét mã tem QR dán trực tiếp trên thân vỏ máy móc ngoài xưởng.",
                "permission": "asset:read",
                "form_fields": [
                    "Tự động nhận diện chuỗi ký tự mã QR (VD: QR-PUMP-2023-088) qua luồng camera trực tiếp."
                ],
                "notes": "Sau khi camera bắt nét mã QR, hệ thống lập tức mở hồ sơ chi tiết thiết bị, hiển thị lịch sử bảo dưỡng và các phụ tùng tương thích.",
                "action_triggers": [
                    "quét qr code bấm ở đâu",
                    "nút quét qr code ở đâu",
                    "chỉ tôi quét qr code máy móc",
                    "cách dùng nút quét qr",
                    "làm sao quét mã qr tài sản",
                    "hướng dẫn quét qr code thiết bị",
                    "bấm vào đâu để quét mã qr"
                ]
            },
            {
                "name": "Chỉnh Sửa Tài Sản",
                "location": "Thanh công cụ chi tiết tài sản bên phải (Right Pane) khi đang chọn một máy trên cây tài sản.",
                "trigger_workflow": "Mở lại modal thông tin tài sản với dữ liệu cũ để cập nhật thông số và vị trí.",
                "permission": "asset:update hoặc asset:write",
                "form_fields": [
                    "Cập nhật thông số kỹ thuật, công suất định mức, dải áp suất.",
                    "Thay đổi trạng thái vận hành máy: Hoạt động (OPERATIONAL), Bảo trì (MAINTENANCE), Hỏng hóc (BROKEN), Thanh lý (DECOMMISSIONED).",
                    "Cập nhật vị trí lắp đặt và gán khu vực bản đồ 2D mới."
                ],
                "notes": "Mọi thay đổi đều được ghi vết tự động vào nhật ký kiểm toán Audit Logs.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút sửa tài sản",
                    "cách dùng nút chỉnh sửa tài sản",
                    "sửa thông tin tài sản ở đâu",
                    "nút sửa máy nằm ở đâu",
                    "cách điền form sửa tài sản",
                    "làm sao để sửa thông tin tài sản",
                    "hướng dẫn chỉnh sửa thiết bị"
                ]
            }
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
            "menu phiếu bảo trì ở đâu"
        ],
        "summary": "Quản lý toàn diện vòng đời phiếu bảo trì sửa chữa với 6 trạng thái chuẩn CMMS và các thuật toán điều phối thông minh.",
        "features": [
            "Quy trình vòng đời 6 trạng thái chuẩn: CREATED (Mới tạo) -> ASSIGNED (Đã giao việc) -> IN_PROGRESS (Đang sửa chữa) -> ON_HOLD (Tạm dừng/Chờ vật tư) -> COMPLETED (Đã hoàn thành) -> CANCELLED (Đã hủy).",
            "Bảng danh sách phiếu bảo trì: Phân loại theo mức độ ưu tiên (CRITICAL, HIGH, MEDIUM, LOW).",
            "Bộ lọc đa chiều: Lọc theo trạng thái, nhóm thợ phụ trách, loại bảo trì (Corrective vs PM), khoảng thời gian.",
            "Modal chi tiết phiếu WO: Xem mô tả sự cố, tài sản liên quan, kỹ thuật viên phụ trách, nhật ký thao tác và danh sách vật tư đã xuất dùng."
        ],
        "actions": [
            "Nút '+ Tạo phiếu bảo trì': Mở modal lập phiếu sửa chữa mới, chọn thiết bị, mức độ ưu tiên và mô tả sự cố.",
            "Nút 'Điều phối tức thời 1-1' (Hungarian Algorithm): Ghép cặp tối ưu 1 thợ - 1 việc cho các sự cố khẩn cấp bằng giải thuật Kuhn-Munkres.",
            "Nút 'Lập lịch cả ca nhiều việc' (Genetic Algorithm): Phân bổ tối ưu danh mục công việc cho ca trực 8 tiếng bằng giải thuật Di truyền GA.",
            "Nút 'Tối ưu lộ trình di chuyển' (TSP Routing): Sắp xếp thứ tự các điểm dừng sửa chữa tối ưu theo sơ đồ mặt bằng.",
            "Nút 'Giao việc (Assign)': Phân công kỹ thuật viên hoặc đội thợ tiếp nhận phiếu.",
            "Nút 'Bắt đầu sửa chữa (Start)': Chuyển trạng thái sang Đang sửa chữa (IN_PROGRESS) và ghi nhận thời gian bắt đầu.",
            "Nút 'Nghiệm thu & Hoàn thành (Complete)': Kỹ sư trưởng phê duyệt kết quả sửa chữa, chuyển trạng thái COMPLETED."
        ],
        "action_details": [
            {
                "name": "Tạo Phiếu Mới (Tạo Phiếu Bảo Trì)",
                "location": "Góc trên bên phải thanh Header của màn hình Phiếu Bảo Trì (/portal/work-orders/), nút màu xanh chính.",
                "trigger_workflow": "Mở popup modal 'Tạo Phiếu Bảo Trì Mới' (#wo-modal).",
                "permission": "work_order:create",
                "form_fields": [
                    "Tiêu đề phiếu (wo-title, *bắt buộc): Mô tả ngắn gọn sự cố hoặc nội dung công việc (VD: Thay phốt cơ khí bơm nước B1, Sửa rò rỉ van dầu).",
                    "Thiết bị / Tài sản (wo-asset-id, *bắt buộc): Chọn máy móc gặp sự cố từ cây tài sản.",
                    "Mức độ ưu tiên (wo-priority, *bắt buộc): Khẩn cấp (CRITICAL), Cao (HIGH), Trung bình (MEDIUM), Thấp (LOW).",
                    "Loại công việc (wo-work-type): Sửa chữa sự cố (CORRECTIVE) hoặc Bảo dưỡng định kỳ (PREVENTIVE).",
                    "Mô tả chi tiết sự cố (wo-description): Hiện tượng máy có tiếng kêu lạ, nhiệt độ tăng vọt, mã lỗi báo trên màn hình PLC.",
                    "Phân công kỹ thuật viên (wo-assigned-to, tùy chọn): Chỉ định thợ tiếp nhận việc ngay khi lập phiếu.",
                    "Hạn hoàn thành (wo-due-date): Ngày giờ chót phải hoàn thành sửa chữa để bàn giao máy cho sản xuất."
                ],
                "notes": "Phiếu mới lập luôn ở trạng thái CREATED. Bấm nút 'Lưu Phiếu' để tạo mới hoặc 'Hủy' để đóng modal.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút tạo phiếu bảo trì đi",
                    "chỉ tôi sử dụng nút tạo phiếu bảo trì",
                    "cách dùng nút tạo phiếu mới",
                    "làm sao để tạo phiếu bảo trì",
                    "làm thế nào để tạo phiếu bảo trì mới",
                    "nút tạo phiếu bảo trì ở đâu",
                    "nút tạo phiếu bảo trì nằm ở đâu",
                    "form tạo phiếu bảo trì điền gì",
                    "form tạo phiếu bảo trì có các trường nào",
                    "form tạo phiếu wo điền gì",
                    "hướng dẫn tạo phiếu sửa chữa",
                    "cách lập phiếu wo mới",
                    "quyền bấm nút tạo phiếu bảo trì"
                ]
            },
            {
                "name": "Điều Phối Tức Thời 1-1 (Hungarian Algorithm)",
                "location": "Thanh công cụ Header trên cùng của trang Phiếu Bảo Trì (/portal/work-orders/), nút gradient tím-xanh (#btn-hungarian-optimize).",
                "trigger_workflow": "Mở Modal 'Điều phối tức thời 1-1' (Hungarian Kuhn-Munkres).",
                "permission": "work_order:reassign (Yêu cầu tenant kích hoạt enable_ai_hungarian)",
                "form_fields": [
                    "Chọn danh sách các phiếu bảo trì khẩn cấp (CRITICAL/HIGH) đang ở trạng thái CREATED.",
                    "Chọn danh sách kỹ thuật viên đang trực sẵn sàng trong ca.",
                    "Xem ma trận điểm tối ưu ghép cặp (kỹ năng thợ, khoảng cách vị trí máy, tải công việc hiện tại).",
                    "Nút 'Xác nhận điều phối': Tự động gán việc 1-1 và chuyển trạng thái các phiếu sang ASSIGNED."
                ],
                "notes": "Áp dụng giải thuật Kuhn-Munkres giải bài toán phân công tối ưu nhị phân trong thời gian O(n^3).",
                "action_triggers": [
                    "chỉ tôi sử dụng nút điều phối 1-1 hungarian",
                    "nút điều phối 1-1 hungarian bấm ở đâu",
                    "nút điều phối 1-1 hungarian ở đâu và ai được bấm",
                    "nút hungarian ở đâu và ai được bấm",
                    "cách dùng nút ghép việc hungarian",
                    "làm sao để bấm nút hungarian",
                    "hướng dẫn điều phối tức thời 1-1",
                    "điều phối tức thời 1-1 hoạt động thế nào",
                    "nút hungarian nằm ở đâu"
                ]
            },
            {
                "name": "Lập Lịch Cả Ca Nhiều Việc (Genetic Algorithm - GA)",
                "location": "Thanh công cụ Header trên cùng của trang Phiếu Bảo Trì (/portal/work-orders/), nút gradient xanh lá (#btn-ga-scheduler).",
                "trigger_workflow": "Mở Drawer/Modal 'Lập lịch ca trực GA' (Genetic Algorithm).",
                "permission": "work_order:reassign (Yêu cầu tenant kích hoạt enable_ai_genetic)",
                "form_fields": [
                    "Chọn Ca trực làm việc: Ca 1 (Sáng), Ca 2 (Chiều), hoặc Ca 3 (Đêm).",
                    "Chọn danh sách công việc cần phân bổ cho ca 8 tiếng.",
                    "Số thế hệ tiến hóa Generations (mặc định 100 thế hệ).",
                    "Tỷ lệ đột biến Mutation Rate (mặc định 0.05).",
                    "Nút 'Chạy giải thuật GA': Khởi chạy giải thuật Di truyền để sinh lịch trình cân bằng tải và tối ưu thời gian di chuyển."
                ],
                "notes": "Tối ưu hóa đa mục tiêu: Cân bằng số giờ làm của thợ, giảm thiểu thời gian chờ và ưu tiên phiếu có mức độ nghiêm trọng cao.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút lập lịch ca trực ga",
                    "nút lập lịch ca trực ga bấm ở đâu",
                    "nút lập lịch ca trực ga bấm chỗ nào",
                    "lập lịch ca trực ga bấm chỗ nào",
                    "lập lịch ca trực ga dùng thế nào",
                    "cách dùng nút genetic algorithm",
                    "lập lịch cả ca nhiều việc ở đâu",
                    "làm sao để chạy lập lịch ga",
                    "hướng dẫn lập lịch ca trực ga",
                    "hướng dẫn bấm nút lập lịch ca trực",
                    "ai được bấm nút lập lịch ga"
                ]
            },
            {
                "name": "Tối Ưu Lộ Trình Di Chuyển (TSP Routing)",
                "location": "Thanh công cụ Header trang Phiếu Bảo Trì (/portal/work-orders/), nút gradient màu cam (#btn-tsp-routing).",
                "trigger_workflow": "Mở Modal 'Tối ưu lộ trình di chuyển' (Traveling Salesperson Problem - TSP).",
                "permission": "work_order:execute hoặc system:admin (Yêu cầu tenant kích hoạt enable_tsp_routing)",
                "form_fields": [
                    "Chọn danh sách các phiếu bảo trì / điểm máy cần ghé thăm trong lượt đi.",
                    "Điểm xuất phát (Start Location): Kho dụng cụ, Phòng cơ điện, hoặc Cửa phân xưởng.",
                    "Nút 'Tính toán lộ trình ngắn nhất': Hiển thị danh sách thứ tự dừng tối ưu và đường vẽ sơ đồ mặt bằng."
                ],
                "notes": "Giúp giảm tới 35% thời gian di chuyển qua lại giữa các máy móc trong nhà xưởng rộng.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút tối ưu lộ trình tsp",
                    "nút tối ưu lộ trình di chuyển bấm ở đâu",
                    "nút tối ưu lộ trình tsp bấm ở đâu",
                    "cách dùng nút tsp routing",
                    "làm sao để sắp xếp thứ tự lộ trình di chuyển",
                    "hướng dẫn tối ưu đường đi sửa chữa",
                    "tối ưu lộ trình di chuyển ở đâu"
                ]
            },
            {
                "name": "Giao Việc (Assign)",
                "location": "Cột Thao tác trên từng dòng của bảng Phiếu Bảo Trì hoặc trong panel chi tiết phiếu WO.",
                "trigger_workflow": "Mở popup chọn kỹ thuật viên để gán trách nhiệm xử lý phiếu.",
                "permission": "work_order:reassign hoặc work_order:create",
                "form_fields": [
                    "Kỹ thuật viên phụ trách (*bắt buộc): Chọn nhân sự từ danh sách thợ có chuyên môn phù hợp.",
                    "Ghi chú giao việc: Lưu ý an toàn lao động, trang bị đồ bảo hộ chuyên dụng.",
                    "Trạng thái phiếu: Tự động chuyển từ CREATED sang ASSIGNED."
                ],
                "notes": "Kỹ thuật viên được gán sẽ nhận thông báo tức thời trên ứng dụng di động để tiếp nhận công việc.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút giao việc đi",
                    "chỉ tôi sử dụng nút giao việc",
                    "nút giao việc bấm ở đâu",
                    "nút giao việc ở đâu",
                    "nút giao việc nằm ở đâu",
                    "cách dùng nút giao việc",
                    "cách bấm nút giao việc",
                    "làm sao để giao việc cho thợ",
                    "nút giao việc ở đâu và ai được bấm",
                    "hướng dẫn thao tác giao việc",
                    "ai có quyền bấm nút giao việc"
                ]
            },
            {
                "name": "Bắt Đầu Sửa Chữa (Start)",
                "location": "Nằm trong màn hình chi tiết phiếu bảo trì đang ở trạng thái ASSIGNED.",
                "trigger_workflow": "Kỹ thuật viên xác nhận bắt đầu thao tác tại hiện trường, chuyển trạng thái từ ASSIGNED sang IN_PROGRESS và bấm giờ thực tế.",
                "permission": "work_order:execute (Kỹ thuật viên được phân công phiếu)",
                "form_fields": [
                    "Xác nhận đã tiếp cận máy và bắt đầu sửa chữa, không cần điền form phức tạp."
                ],
                "notes": "Hệ thống ghi nhận thời điểm bấm nút để phục vụ đo lường thời gian trung bình sửa chữa (MTTR).",
                "action_triggers": [
                    "chỉ tôi sử dụng nút bắt đầu sửa chữa",
                    "nút bắt đầu sửa chữa bấm ở đâu",
                    "bắt đầu sửa chữa bấm nút nào và chuyển trạng thái gì",
                    "cách dùng nút start sửa chữa",
                    "làm sao chuyển trạng thái in progress",
                    "khi nào bấm nút bắt đầu sửa chữa",
                    "hướng dẫn bấm bắt đầu sửa chữa"
                ]
            },
            {
                "name": "Nghiệm Thu & Hoàn Thành (Complete)",
                "location": "Nằm trong modal chi tiết phiếu bảo trì khi sửa xong máy.",
                "trigger_workflow": "Mở form hoàn tất và nghiệm thu công việc sửa chữa để đóng phiếu.",
                "permission": "work_order:approve hoặc work_order:execute",
                "form_fields": [
                    "Giải pháp kỹ thuật đã thực hiện (Resolution Notes, *bắt buộc): Mô tả rõ đã thay thế phụ tùng gì, cách cân chỉnh và phương pháp khắc phục.",
                    "Thời gian dừng máy thực tế (Downtime minutes): Số phút dây chuyền phải ngừng vận hành.",
                    "Xác nhận chạy thử đạt yêu cầu an toàn: Tích chọn kiểm tra an toàn sau sửa chữa.",
                    "Trạng thái phiếu: Chuyển sang COMPLETED (Đã hoàn thành)."
                ],
                "notes": "Nội dung giải pháp đạt chuẩn sẽ tự động được gửi sang Hàng đợi thẩm định tri thức AI (Tacit Curation Queue) để Kỹ sư trưởng duyệt thành Tri thức Vàng.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút hoàn thành phiếu",
                    "nút hoàn thành phiếu bảo trì ở đâu",
                    "nghiệm thu hoàn thành phiếu sửa chữa cần điền những gì",
                    "cách nghiệm thu phiếu wo",
                    "form hoàn thành phiếu bảo trì điền gì",
                    "làm sao để hoàn tất phiếu sửa chữa",
                    "hướng dẫn nghiệm thu phiếu bảo trì"
                ]
            }
        ]
    },
    {
        "id": "portal_inventory",
        "title": "Trang Kho Vật Tư & Phụ Tùng (Inventory Management)",
        "template": "inventory.html",
        "route_url": "/portal/inventory/",
        "permission": "inventory:read (Xem), inventory:write (Nhập/Xuất/Điều chỉnh kho), inventory:create (Thêm mới)",
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
            "cách nhập xuất vật tư phụ tùng",
            "menu kho vật tư phụ tùng ở đâu",
            "menu kho vật tư ở đâu"
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
            "Nút '+ Thêm Vật Tư Mới': Tạo mới bản ghi vật tư phụ tùng vào danh mục kho.",
            "Nút 'Nhập kho mới': Tạo phiếu nhập kho vật tư từ nhà cung cấp.",
            "Nút 'Xuất kho cho phiếu WO': Trừ tồn kho vật tư phục vụ công tác sửa chữa hiện trường.",
            "Nút 'Kiểm kê điều chỉnh kho': Cân chỉnh số lượng tồn kho sổ sách với kiểm kê thực tế.",
            "Nút 'Xuất danh sách Excel': Tải báo cáo tồn kho và danh sách vật tư cần đặt mua bổ sung."
        ],
        "action_details": [
            {
                "name": "Thêm Vật Tư Mới",
                "location": "Góc trên bên phải thanh Header của màn hình Quản Lý Vật Tư & Phụ Tùng (/portal/inventory/).",
                "trigger_workflow": "Mở popup modal 'Thêm Mới Vật Tư' (#inventory-modal).",
                "permission": "inventory:create hoặc inventory:write",
                "form_fields": [
                    "Tên vật tư (inv-name, *bắt buộc): Tên linh kiện hoặc phụ tùng (VD: Lọc dầu động cơ, Vòng bi SKF, Phớt cơ khí làm kín).",
                    "Mã phụ tùng SKU (inv-part-number, *bắt buộc): Mã quản lý kho duy nhất (VD: FLT-001, SKF-2210).",
                    "Mặt bằng (inv-floorplan, tùy chọn): Chọn tầng/phân xưởng để lọc danh mục kho lưu trữ.",
                    "Khu vực / Nơi cất giữ vật tư (inv-location, tùy chọn): Chọn kệ, phòng kho, trạm phụ trợ nơi cất giữ linh kiện kèm số tầng.",
                    "Mô tả chi tiết (inv-desc): Quy cách kỹ thuật, xuất xứ, khuyến cáo bảo quản.",
                    "Số lượng tồn kho (inv-quantity, *bắt buộc): Số lượng nhập kho thực tế ban đầu (số nguyên >= 0).",
                    "Đơn giá VNĐ (inv-unit-cost, *bắt buộc): Giá nhập của 1 đơn vị vật tư tính theo Việt Nam Đồng."
                ],
                "notes": "Bấm nút 'Lưu Vật Tư' (#btn-save-inv) để tạo mới, hoặc nút 'Hủy' để đóng modal.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút thêm vật tư đi",
                    "chỉ tôi sử dụng nút thêm vật tư",
                    "chỉ tôi thêm vật tư",
                    "cách dùng nút thêm vật tư mới",
                    "cách dùng nút thêm vật tư",
                    "làm sao để bấm nút thêm vật tư",
                    "làm sao để thêm vật tư mới",
                    "làm sao để thêm vật tư",
                    "nút thêm vật tư ở đâu",
                    "nút thêm vật tư bấm ở đâu",
                    "nút thêm vật tư nằm ở đâu",
                    "form thêm vật tư điền gì",
                    "form này điền gì",
                    "quyền bấm nút thêm vật tư",
                    "nút thêm vật tư cần quyền gì",
                    "thêm vật tư mới như thế nào",
                    "hướng dẫn thao tác thêm vật tư",
                    "hướng dẫn thao tác thêm vật tư mới"
                ]
            },
            {
                "name": "Nhập Kho Mới",
                "location": "Thanh công cụ trang Kho vật tư (/portal/inventory/) hoặc nút hành động trên bảng.",
                "trigger_workflow": "Mở form ghi nhận số lượng hàng nhập từ nhà cung cấp về kho.",
                "permission": "inventory:write hoặc Thủ kho (Storekeeper)",
                "form_fields": [
                    "Số lượng nhập thêm (*bắt buộc): Số lượng phụ tùng thực nhận tại kho.",
                    "Đơn giá nhập mới: Cập nhật nếu giá thị trường biến động.",
                    "Mã chứng từ / Hóa đơn: Số phiếu giao nhận từ nhà cung ứng.",
                    "Ghi chú lô hàng: Hạn bảo hành linh kiện, điều kiện lưu kho."
                ],
                "notes": "Tồn kho khả dụng của vật tư sẽ tăng lên tức thì ngay sau khi lưu phiếu nhập.",
                "action_triggers": [
                    "chỉ tôi cách nhập kho mới",
                    "cách nhập kho vật tư",
                    "làm thế nào để nhập kho mới",
                    "nút nhập kho ở đâu",
                    "chỉ tôi thao tác nhập kho",
                    "làm sao để nhập thêm phụ tùng",
                    "form nhập kho điền gì",
                    "hướng dẫn thao tác nhập kho phụ tùng"
                ]
            },
            {
                "name": "Xuất Kho Cho Phiếu WO",
                "location": "Trong tab Vật tư của modal chi tiết Phiếu Bảo Trì hoặc trên màn hình Kho.",
                "trigger_workflow": "Trừ tồn kho linh kiện phụ tùng để cấp phát cho công tác sửa chữa hiện trường.",
                "permission": "inventory:write hoặc work_order:execute",
                "form_fields": [
                    "Mã phiếu bảo trì (*bắt buộc): Chọn phiếu WO cần cấp phát phụ tùng.",
                    "Linh kiện cần xuất: Chọn mã phụ tùng từ danh mục khả dụng.",
                    "Số lượng xuất (*bắt buộc): Không được vượt quá số lượng tồn kho khả dụng hiện tại."
                ],
                "notes": "Hệ thống tự động liên kết mã phiếu bảo trì với vật tư để hạch toán chi phí sửa chữa vào tài sản.",
                "action_triggers": [
                    "cách xuất kho phụ tùng cho phiếu bảo trì",
                    "chỉ tôi dùng nút xuất kho",
                    "nút xuất kho ở đâu",
                    "làm sao để xuất vật tư sửa chữa",
                    "hướng dẫn xuất kho cho phiếu wo",
                    "thao tác xuất kho phụ tùng thế nào"
                ]
            },
            {
                "name": "Kiểm Kê Điều Chỉnh Kho",
                "location": "Thanh công cụ quản lý kho vật tư (/portal/inventory/).",
                "trigger_workflow": "Mở modal cân chỉnh số lượng tồn kho sổ sách với kiểm kê thực tế tại giá kệ.",
                "permission": "inventory:write (Thủ kho hoặc Kỹ sư trưởng)",
                "form_fields": [
                    "Số lượng thực tế kiểm kê (*bắt buộc): Số lượng đếm được thực tế tại giá kệ.",
                    "Lý do điều chỉnh (*bắt buộc): Chọn lý do (Hao hụt tự nhiên, Sai sót nhập liệu, Thất lạc, Hỏng hóc).",
                    "Số biên bản kiểm kê: Mã số biên bản kiểm kê kho định kỳ."
                ],
                "notes": "Mọi thay đổi cân chỉnh tồn kho đều được kiểm toán nghiêm ngặt trong lịch sử giao dịch.",
                "action_triggers": [
                    "cách kiểm kê cân chỉnh số lượng tồn kho thực tế",
                    "chỉ tôi dùng nút kiểm kê kho",
                    "nút kiểm kê kho ở đâu",
                    "cách điều chỉnh tồn kho",
                    "làm sao để cân chỉnh số lượng phụ tùng thực tế",
                    "hướng dẫn thao tác kiểm kê kho"
                ]
            },
            {
                "name": "Xuất Danh Sách Excel Kho",
                "location": "Thanh công cụ bộ lọc của bảng Quản Lý Vật Tư & Phụ Tùng (/portal/inventory/).",
                "trigger_workflow": "Xuất tệp bảng tính Excel (.xlsx) chứa toàn bộ danh mục vật tư, tồn kho, vị trí kệ và danh sách phụ tùng sắp hết.",
                "permission": "inventory:read",
                "form_fields": [
                    "Thao tác 1 chạm trực tiếp, tự động tải xuống file Excel qua trình duyệt."
                ],
                "notes": "Hỗ trợ thủ kho nhanh chóng lập danh sách đặt mua bổ sung các linh kiện dưới mức an toàn (Min-Stock).",
                "action_triggers": [
                    "làm sao để xuất excel kho",
                    "chỉ tôi sử dụng nút xuất excel kho",
                    "nút xuất excel kho ở đâu",
                    "cách tải excel tồn kho vật tư",
                    "hướng dẫn xuất file excel phụ tùng",
                    "xuất danh sách kho ra excel",
                    "xuất excel kho phụ tùng bấm ở đâu"
                ]
            }
        ]
    },
    {
        "id": "portal_workforce_tools",
        "title": "Trang Nhân Lực & Quản Lý Công Cụ (Workforce & Tools)",
        "template": "workforce_tools.html",
        "route_url": "/portal/workforce-tools/",
        "permission": "workforce:read, work_order:read, user:read, tool:read",
        "triggers": [
            "trang nhân lực và công cụ có gì",
            "nhân lực và công cụ có gì",
            "nhân lực & công cụ có gì",
            "trang nhân lực có gì",
            "nhân lực có gì",
            "công cụ có gì",
            "quản lý ca trực kỹ thuật viên",
            "chứng chỉ an toàn",
            "hiệu chuẩn công cụ dụng cụ",
            "menu nhân lực công cụ ở đâu"
        ],
        "summary": "Quản trị đội ngũ kỹ thuật viên xưởng, phân ca trực, chứng chỉ an toàn lao động và quản lý hiệu chuẩn công cụ đo kiểm.",
        "features": [
            "Quản lý kỹ thuật viên: Hồ sơ tay nghề, chuyên môn (Cơ khí, Thủy lực, Điện - Tự động hóa), bậc thợ và trạng thái sẵn sàng.",
            "Bảng xếp ca trực (Shift Scheduling): Lịch trực theo Ca 1 (Sáng), Ca 2 (Chiều), Ca 3 (Đêm) và theo dõi ngày nghỉ.",
            "Hồ sơ chứng chỉ an toàn: Quản lý chứng chỉ an toàn điện cao thế, làm việc trên cao, an toàn áp lực, cảnh báo sắp hết hạn.",
            "Danh mục công cụ chuyên dùng: Quản lý đồng hồ đo vạn năng, máy đo rung chấn, súng đo nhiệt hồng ngoại, cờ lê lực.",
            "Lịch hiệu chuẩn định kỳ: Theo dõi hạn kiểm định và cảnh báo thiết bị quá hạn hiệu chuẩn."
        ],
        "actions": [
            "Nút '+ Thêm Kỹ Năng': Nhập chứng chỉ tay nghề mới cho kỹ thuật viên.",
            "Nút '+ Thêm Mẫu Ca': Định nghĩa khung giờ ca làm việc mới.",
            "Nút '+ Thêm Thiết Bị Serial': Đăng ký dụng cụ đo kiểm có số serial và hạn hiệu chuẩn.",
            "Nút 'Phân ca làm việc': Xếp ca trực hàng tuần cho đội ngũ kỹ thuật viên.",
            "Nút 'Ghi nhận hiệu chuẩn': Cập nhật ngày kiểm định mới nhất và tải lên biên bản hiệu chuẩn."
        ],
        "action_details": [
            {
                "name": "Thêm Kỹ Năng / Chứng Chỉ",
                "location": "Thanh công cụ Quick Action trên Header trang Nhân Lực & Công Cụ (/portal/workforce-tools/), nút 'Thêm Kỹ Năng'.",
                "trigger_workflow": "Mở modal 'Thêm Kỹ Năng / Chứng Chỉ' (#modal-cert).",
                "permission": "workforce:write hoặc user:write",
                "form_fields": [
                    "Mã kỹ năng / chứng chỉ (*bắt buộc): Mã chuẩn hóa (VD: ELEC-HIGH, WELD-6G, PNEU-LV3).",
                    "Tên chứng chỉ / kỹ năng (*bắt buộc): Tên hiển thị (VD: An toàn điện cao thế, Hàn công nghiệp 6G).",
                    "Thời hạn hiệu lực (tháng): Số tháng chứng chỉ có giá trị (VD: 12 tháng, 24 tháng).",
                    "Mô tả tiêu chuẩn: Phạm vi công việc được phép thực hiện khi sở hữu chứng chỉ."
                ],
                "notes": "Hệ thống tự động cảnh báo khi chứng chỉ của kỹ thuật viên sắp hết hạn.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút thêm kỹ năng",
                    "nút thêm kỹ năng ở đâu",
                    "cách dùng nút thêm chứng chỉ",
                    "làm sao để thêm kỹ năng kỹ thuật viên",
                    "form thêm kỹ năng điền gì",
                    "bấm đâu để thêm kỹ năng cho thợ",
                    "thêm kỹ năng cho thợ ở đâu",
                    "cách thêm kỹ năng cho thợ"
                ]
            },
            {
                "name": "Thêm Mẫu Ca Trực",
                "location": "Thanh công cụ Header trang Nhân Lực & Công Cụ, nút 'Thêm Mẫu Ca'.",
                "trigger_workflow": "Mở modal 'Khung Mẫu Ca Trực' (#modal-shift).",
                "permission": "workforce:write",
                "form_fields": [
                    "Mã ca (*bắt buộc): Mã viết tắt (VD: CA1, CA2, CA3, HC).",
                    "Tên ca làm việc (*bắt buộc): Tên ca (VD: Ca Sáng, Ca Chiều, Ca Đêm, Hành chính).",
                    "Giờ bắt đầu - Giờ kết thúc: Khung giờ làm việc (VD: 06:00 - 14:00).",
                    "Ca qua đêm (Overnight): Đánh dấu nếu ca làm việc kéo dài qua 00:00 ngày hôm sau.",
                    "Màu sắc nhận diện: Chọn mã màu để hiển thị trực quan trên bảng ma trận xếp ca."
                ],
                "notes": "Các mẫu ca trực này sẽ được dùng để phân bổ lịch làm việc hàng tuần.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút thêm mẫu ca",
                    "nút thêm mẫu ca ở đâu",
                    "cách dùng nút tạo ca trực",
                    "làm sao để tạo ca trực mới",
                    "form tạo ca trực điền gì"
                ]
            },
            {
                "name": "Phân Ca Làm Việc (Xếp Lịch Trực)",
                "location": "Nhấp trực tiếp vào từng ô ngày của kỹ thuật viên trên bảng ma trận Xếp ca (Tab 2: Ca trực & Bảng xếp ca).",
                "trigger_workflow": "Mở modal 'Xếp lịch làm việc cho KTV' (#modal-schedule).",
                "permission": "workforce:write",
                "form_fields": [
                    "Trạng thái làm việc: Đi làm (ON_DUTY), Nghỉ phép (LEAVE), Nghỉ tuần (OFF).",
                    "Chọn ca làm việc: Ca 1, Ca 2 hoặc Ca 3.",
                    "Khu vực phân xưởng phụ trách (Duty Zone): Chỉ định khu vực xưởng KTV chịu trách nhiệm ứng trực."
                ],
                "notes": "Giúp trưởng phòng cơ điện dễ dàng điều chỉnh lịch làm việc đột xuất khi có nhân sự xin nghỉ.",
                "action_triggers": [
                    "cách xếp lịch trực tuần cho kỹ thuật viên",
                    "chỉ tôi phân ca làm việc cho thợ",
                    "muốn phân ca trực cho thợ thì bấm nút nào",
                    "cách dùng nút xếp ca trực",
                    "nút xếp ca trực ở đâu",
                    "làm sao để xếp lịch trực kỹ thuật viên",
                    "hướng dẫn phân ca làm việc"
                ]
            },
            {
                "name": "Thêm Thiết Bị Serial Đo Kiểm",
                "location": "Góc trên bên phải Header trang Nhân Lực & Công Cụ, nút gradient 'Thêm Thiết Bị Serial'.",
                "trigger_workflow": "Mở modal 'Thêm Serial Thiết Bị Đo Kiểm' (#modal-tool-instance).",
                "permission": "tool:write hoặc workforce:write",
                "form_fields": [
                    "Chọn dòng công cụ (*bắt buộc): Chọn loại thiết bị đo (Đồng hồ vạn năng, Máy đo rung chấn, Cờ lê lực...).",
                    "Số Serial thiết bị (*bắt buộc): Mã seri khắc trên máy đo từ nhà sản xuất.",
                    "Mã tem RFID/QR: Mã định danh gắn trên công cụ để quét mượn trả.",
                    "Ngày hiệu chuẩn gần nhất: Ngày kiểm định gần nhất.",
                    "Hạn hiệu chuẩn tiếp theo (Calibration Due Date): Ngày hết hạn kiểm định.",
                    "Ghi chú tình trạng: Tình trạng độ chính xác và phụ kiện kèm theo."
                ],
                "notes": "Công cụ quá hạn hiệu chuẩn sẽ bị hệ thống cảnh báo đỏ và ngăn không cho điều động vào phiếu bảo trì.",
                "action_triggers": [
                    "chỉ tôi thêm thiết bị serial đo kiểm mới",
                    "chỉ tôi sử dụng nút thêm thiết bị serial",
                    "nút thêm thiết bị serial ở đâu",
                    "cách dùng nút thêm máy đo kiểm",
                    "làm sao để thêm serial công cụ đo",
                    "form thêm công cụ serial điền gì"
                ]
            },
            {
                "name": "Ghi Nhận Hiệu Chuẩn Công Cụ",
                "location": "Nằm trên từng dòng công cụ đo trong Tab 3 (Dụng cụ & Kiểm định Serial).",
                "trigger_workflow": "Mở modal cập nhật kết quả kiểm định định kỳ thiết bị đo kiểm.",
                "permission": "tool:write",
                "form_fields": [
                    "Ngày kiểm định mới: Ngày đơn vị đo lường cấp chứng thư kiểm định.",
                    "Hạn kiểm định kế tiếp: Ngày hết hạn tem kiểm định mới.",
                    "Trạng thái kiểm định: Đạt chuẩn (VALID) hoặc Không đạt (EXPIRED).",
                    "Đính kèm biên bản hiệu chuẩn: Tải lên file PDF hoặc ảnh chụp chứng chỉ kiểm định."
                ],
                "notes": "Đảm bảo tuân thủ tiêu chuẩn chất lượng ISO 9001 và an toàn thiết bị đo.",
                "action_triggers": [
                    "chỉ tôi ghi nhận hiệu chuẩn công cụ",
                    "nút ghi nhận hiệu chuẩn ở đâu",
                    "cách dùng nút cập nhật kiểm định",
                    "làm sao để ghi nhận hiệu chuẩn máy đo",
                    "hướng dẫn cập nhật hạn kiểm định"
                ]
            }
        ]
    },
    {
        "id": "portal_pm_plans",
        "title": "Trang Kế Hoạch Bảo Trì Định Kỳ (PM Plans)",
        "template": "pm_plans.html",
        "route_url": "/portal/pm-plans/",
        "permission": "pm_plan:read (Xem), pm_plan:write / pm_plan:create (Thêm/Sửa/Lập lịch)",
        "triggers": [
            "trang kế hoạch pm có gì",
            "kế hoạch pm có gì",
            "kế hoạch pm",
            "bảo trì định kỳ có gì",
            "bảo trì định kỳ",
            "hướng dẫn tạo kế hoạch pm",
            "lập lịch bảo trì theo giờ chạy máy",
            "tự động sinh phiếu wo định kỳ",
            "menu kế hoạch pm ở đâu"
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
        ],
        "action_details": [
            {
                "name": "Tạo Kế Hoạch PM Mới",
                "location": "Góc trên bên phải Header trang Kế Hoạch PM (/portal/pm-plans/), nút 'Tạo Kế Hoạch Mới'.",
                "trigger_workflow": "Mở popup modal 'Tạo Kế Hoạch Bảo Trì Định Kỳ' (#pm-modal).",
                "permission": "pm_plan:create hoặc pm_plan:write",
                "form_fields": [
                    "Tên kế hoạch (pm-name, *bắt buộc): Tên quy trình bảo dưỡng (VD: Bảo trì định kỳ máy bơm 3 tháng, Thay dầu máy nén khí 500 giờ).",
                    "Loại kích hoạt (pm-trigger-type, *bắt buộc): Định kỳ thời gian (TIME - Ngày, Tuần, Tháng, Năm) hoặc Theo chỉ số vận hành (METER - Số giờ chạy máy).",
                    "Chu kỳ lặp lại (pm-interval-value & unit, *bắt buộc): Khoảng cách và đơn vị (VD: 3 tháng hoặc 500 giờ).",
                    "Ngăn sinh phiếu nếu còn phiếu đang mở (suppress_if_pending): Tích chọn để tránh sinh nhiều phiếu trùng lặp khi kỳ trước chưa sửa xong.",
                    "Danh sách máy móc áp dụng: Tích chọn máy hoặc lọc theo mặt bằng/phân xưởng để gán kế hoạch.",
                    "Checklist các bước kiểm tra: Thêm từng công việc kiểm tra kèm loại đo kiểm (PASS/FAIL hoặc Đo số liệu) và ngưỡng chuẩn cho phép.",
                    "Phụ tùng & Dụng cụ yêu cầu: Chọn vật tư phụ tùng cần chuẩn bị sẵn khi phiếu kích hoạt."
                ],
                "notes": "Kế hoạch sau khi lưu sẽ tự động phát hành phiếu WO khi đến hạn hoặc khi máy chạy đủ số giờ quy định.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút tạo kế hoạch pm đi",
                    "chỉ tôi sử dụng nút tạo kế hoạch pm",
                    "cách dùng nút tạo kế hoạch mới",
                    "làm sao để tạo kế hoạch pm",
                    "nút tạo kế hoạch pm ở đâu",
                    "nút tạo kế hoạch pm cần quyền gì",
                    "form kế hoạch pm điền gì",
                    "hướng dẫn tạo kế hoạch bảo dưỡng định kỳ",
                    "lập lịch bảo trì định kỳ pm làm thế nào"
                ]
            },
            {
                "name": "Chạy Kích Hoạt Thủ Công PM",
                "location": "Nằm trên từng dòng của bảng danh sách Kế hoạch PM trong Tab Kế hoạch PM (/portal/pm-plans/).",
                "trigger_workflow": "Phát hành ngay lập tức một Phiếu Bảo Trì (Work Order) theo đúng checklist và vật tư của kế hoạch mà không cần chờ đến hạn lịch.",
                "permission": "pm_plan:write hoặc Kỹ sư trưởng",
                "form_fields": [
                    "Xác nhận kích hoạt sinh phiếu ngay cho các thiết bị được gán trong kế hoạch."
                ],
                "notes": "Hữu ích khi nhà máy có đợt dừng máy đột xuất và muốn tranh thủ làm bảo dưỡng trước lịch.",
                "action_triggers": [
                    "chỉ tôi kích hoạt thủ công sinh phiếu wo từ kế hoạch pm",
                    "chỉ tôi kích hoạt thủ công kế hoạch pm",
                    "nút chạy kích hoạt thủ công ở đâu",
                    "cách dùng nút sinh phiếu ngay từ pm",
                    "làm sao để chạy ngay kế hoạch bảo dưỡng",
                    "hướng dẫn kích hoạt thủ công pm"
                ]
            },
            {
                "name": "Ghi Nhận Chỉ Số Đồng Hồ (Log Meter)",
                "location": "Nằm trong màn hình theo dõi đồng hồ đo hoặc hồ sơ máy móc.",
                "trigger_workflow": "Mở form ghi nhận số giờ chạy máy thực tế lấy từ đồng hồ đo công tơ mét.",
                "permission": "asset:write hoặc pm_plan:write",
                "form_fields": [
                    "Số giờ chạy máy hiện tại (*bắt buộc): Chỉ số đọc trên đồng hồ đo thực tế tại tủ điện máy.",
                    "Ngày giờ ghi nhận: Thời điểm đọc số đo.",
                    "Ghi chú tình trạng đồng hồ: Báo cáo nếu đồng hồ bị kẹt hoặc thay mới."
                ],
                "notes": "Nếu số giờ chạy máy vượt ngưỡng kích hoạt của kế hoạch PM dạng METER, hệ thống sẽ tự động phát hành lệnh bảo dưỡng.",
                "action_triggers": [
                    "chỉ tôi ghi nhận chỉ số đồng hồ",
                    "nút cập nhật chỉ số đồng hồ ở đâu",
                    "cách dùng nút log meter",
                    "làm sao nhập giờ chạy máy",
                    "hướng dẫn ghi nhận chỉ số vận hành"
                ]
            }
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
            "xuất báo cáo excel pdf",
            "menu báo cáo ở đâu"
        ],
        "summary": "Trung tâm phân tích hiệu suất thiết bị toàn diện, chỉ số độ tin cậy bảo trì và chi phí vận hành nhà máy.",
        "features": [
            "Chỉ số OEE: Hiệu suất thiết bị tổng thể (Sẵn sàng - Hiệu suất - Chất lượng).",
            "Chỉ số MTBF: Thời gian trung bình giữa các lần hư hỏng sự cố.",
            "Chỉ số MTTR: Thời gian trung bình để hoàn thành một ca sửa chữa.",
            "Phân tích chi phí bảo trì: Tỷ trọng chi phí nhân công, chi phí linh kiện phụ tùng và tổng thiệt hại do dừng máy (Downtime).",
            "Báo cáo tỷ lệ hoàn thành bảo dưỡng định kỳ (PM Compliance Rate)."
        ],
        "actions": [
            "Nút 'Lọc khoảng thời gian': Xem báo cáo theo Tháng, Quý, Năm hoặc khoảng ngày tùy chọn.",
            "Nút 'Xuất Excel': Tải toàn bộ dữ liệu phân tích ra bảng tính Excel phục vụ làm báo cáo quản trị.",
            "Nút 'In / Xuất PDF': Xuất báo cáo trang bìa đồ thị chuyên nghiệp."
        ],
        "action_details": [
            {
                "name": "Xuất Excel Báo Cáo",
                "location": "Góc trên bên phải thanh điều hướng trang Báo Cáo & Phân Tích (/portal/reports/).",
                "trigger_workflow": "Kết xuất toàn bộ số liệu thống kê chỉ số OEE, MTBF, MTTR và chi phí bảo trì ra bảng tính Excel (.xlsx).",
                "permission": "reports:read",
                "form_fields": [
                    "Tự động tạo file Excel dựa trên khoảng thời gian và phân xưởng đang lọc."
                ],
                "notes": "Tệp tải về chứa đầy đủ các bảng dữ liệu chi tiết phục vụ cho công tác làm báo cáo quản trị tuần/tháng.",
                "action_triggers": [
                    "xuất báo cáo oee mtbf mttr ra bảng tính excel ở đâu",
                    "làm sao để xuất excel báo cáo",
                    "chỉ tôi sử dụng nút xuất excel báo cáo",
                    "nút xuất excel báo cáo ở đâu",
                    "cách xuất file excel báo cáo oee",
                    "hướng dẫn tải báo cáo kpi ra excel"
                ]
            }
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
            "tối ưu thời điểm thanh lý thay mới máy",
            "menu dự báo chi phí ở đâu"
        ],
        "summary": "Ứng dụng mô hình kinh tế kỹ thuật dự báo chi phí bảo trì tương lai và phân tích chi phí vòng đời thiết bị (LCC).",
        "features": [
            "Mô hình chi phí vòng đời LCC: Tổng hợp chi phí mua sắm ban đầu (CAPEX), chi phí vận hành bảo dưỡng (OPEX), và giá trị thanh lý.",
            "Dự báo xu hướng chi phí bảo dưỡng trong 12 - 36 tháng tới dựa trên độ tuổi máy móc và tần suất hỏng hóc.",
            "Điểm kinh tế tối ưu thay thế thiết bị: Xác định thời điểm chi phí sửa chữa vượt quá hiệu quả đầu tư máy mới."
        ],
        "actions": [
            "Nút 'Chạy mô hình dự báo': Áp dụng thuật toán dự toán chi phí bảo trì cho năm tài chính tiếp theo.",
            "Nút 'So sánh phương án LCC': Đặt lên bàn cân phương án tiếp tục đại tu sửa chữa so với mua mới."
        ],
        "action_details": [
            {
                "name": "Chạy Mô Hình Dự Báo Chi Phí",
                "location": "Thanh công cụ trang Dự Báo Chi Phí (/portal/cost-forecasting/), nút 'Chạy mô hình dự báo'.",
                "trigger_workflow": "Kích hoạt mô hình toán kinh tế kỹ thuật dự toán chi phí bảo trì trong 12 - 36 tháng tới.",
                "permission": "cost_forecast:read hoặc reports:read",
                "form_fields": [
                    "Khoảng thời gian dự báo: 12 tháng, 24 tháng hoặc 36 tháng.",
                    "Tỷ lệ lạm phát / trượt giá phụ tùng dự kiến (%/năm).",
                    "Danh mục dây chuyền / phân xưởng cần dự toán."
                ],
                "notes": "Kết quả dự báo hiển thị biểu đồ xu hướng CAPEX vs OPEX và điểm kinh tế tối ưu thay thế máy mới.",
                "action_triggers": [
                    "chạy mô hình dự toán chi phí vòng đời lcc bấm vào đâu",
                    "chỉ tôi chạy mô hình dự báo chi phí",
                    "nút chạy dự báo chi phí ở đâu",
                    "cách dùng nút dự toán chi phí lcc",
                    "làm sao để chạy mô hình dự báo chi phí",
                    "hướng dẫn chạy dự báo chi phí bảo trì"
                ]
            }
        ]
    },
    {
        "id": "portal_users",
        "title": "Trang Quản Lý Người Dùng (Users Management)",
        "template": "users.html",
        "route_url": "/portal/users/",
        "permission": "user:read (Xem), user:write / user:create (Thêm/Sửa/Khóa tài khoản)",
        "triggers": [
            "trang người dùng có gì",
            "người dùng có gì",
            "người dùng",
            "quản lý người dùng có gì",
            "quản lý người dùng",
            "tạo tài khoản nhân viên",
            "khóa mở khóa người dùng",
            "menu người dùng ở đâu"
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
        ],
        "action_details": [
            {
                "name": "Thêm Người Dùng Mới",
                "location": "Góc trên bên phải thanh Header trang Quản Lý Người Dùng (/portal/users/).",
                "trigger_workflow": "Mở modal tạo mới tài khoản nhân sự cho nhân viên.",
                "permission": "user:write hoặc user:create",
                "form_fields": [
                    "Họ và tên (*bắt buộc): Họ tên đầy đủ của nhân sự.",
                    "Tên đăng nhập Username (*bắt buộc): Tên dùng để đăng nhập hệ thống.",
                    "Email (*bắt buộc): Hộp thư điện tử nhận thông báo công việc.",
                    "Số điện thoại: Số liên lạc khi có sự cố khẩn cấp.",
                    "Vai trò đảm nhiệm (*bắt buộc): Chọn vai trò (Kỹ sư trưởng, Kỹ thuật viên, Thủ kho...).",
                    "Mật khẩu ban đầu (*bắt buộc): Mật khẩu đăng nhập khởi tạo."
                ],
                "notes": "Bấm 'Lưu người dùng' để khởi tạo. Nhân viên có thể đổi lại mật khẩu sau lần đăng nhập đầu tiên.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút thêm người dùng mới",
                    "nút thêm người dùng ở đâu",
                    "cách dùng nút tạo tài khoản nhân viên",
                    "làm sao để thêm người dùng mới",
                    "form thêm người dùng điền gì",
                    "hướng dẫn tạo tài khoản nhân viên"
                ]
            }
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
            "ma trận quyền hạn hệ thống",
            "menu phân quyền ở đâu"
        ],
        "summary": "Quản lý hệ thống phân quyền dựa trên vai trò (RBAC) với ma trận quyền hạn chi tiết đến từng thao tác.",
        "features": [
            "Danh sách vai trò: Kỹ sư trưởng, Kỹ thuật viên bảo trì, Thủ kho, Giám sát sản xuất, Quản trị viên.",
            "Ma trận quyền hạn phân hệ: Tài sản (asset), Phiếu bảo trì (work_order), Kho vật tư (inventory), Kế hoạch PM (pm_plan), Báo cáo (reports), Tri thức AI (assistant:manage_knowledge), Người dùng (user), Vai trò (role)."
        ],
        "actions": [
            "Nút '+ Tạo vai trò mới': Thiết lập chức danh mới và tích chọn các quyền hạn tương ứng trong ma trận.",
            "Nút 'Chỉnh sửa quyền': Bổ sung hoặc thu hồi quyền hạn của vai trò.",
            "Nút 'Xóa vai trò': Loại bỏ vai trò không còn sử dụng."
        ],
        "action_details": [
            {
                "name": "Tạo Vai Trò Mới",
                "location": "Góc trên bên phải Header trang Phân Quyền (/portal/roles/).",
                "trigger_workflow": "Mở modal khởi tạo chức danh và phân quyền ma trận RBAC.",
                "permission": "role:write hoặc Admin hệ thống",
                "form_fields": [
                    "Tên vai trò (*bắt buộc): Tên chức danh (VD: Trưởng ca cơ điện, Nhân viên kho phụ).",
                    "Mô tả chức năng: Trách nhiệm và quyền hạn của vai trò.",
                    "Ma trận quyền hạn: Tích chọn các quyền cụ thể trên từng phân hệ (Tài sản, Phiếu bảo trì, Kho vật tư, Kế hoạch PM, Tri thức AI...)."
                ],
                "notes": "Các tài khoản được gán vai trò này sẽ ngay lập tức được cấp các quyền tương ứng.",
                "action_triggers": [
                    "thêm vai trò mới và phân quyền rbac cho thợ làm thế nào",
                    "chỉ tôi sử dụng nút tạo vai trò mới",
                    "nút tạo vai trò mới ở đâu",
                    "cách dùng nút tạo vai trò phân quyền",
                    "cách tạo vai trò mới trên hệ thống",
                    "làm sao để tạo vai trò mới",
                    "form tạo vai trò điền gì",
                    "ai có quyền phân quyền"
                ]
            }
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
            "nhóm thiết bị máy móc",
            "menu cấu hình tài sản ở đâu"
        ],
        "summary": "Thiết lập cấu hình danh mục phân loại máy móc và sơ đồ vị trí không gian địa lý của các nhà xưởng.",
        "features": [
            "Quản lý Danh mục tài sản: Động cơ điện, Bơm thủy lực, Máy nén khí, Băng tải công nghiệp, Máy CNC, Lò nhiệt luyện.",
            "Quản lý Vị trí vật lý: Danh sách Tòa nhà, Phân xưởng sản xuất, Khu vực phụ trợ, Trạm cấp nguồn điện."
        ],
        "actions": [
            "Nút '+ Thêm phân loại / danh mục mới': Tạo mới nhóm phân loại máy móc kèm biểu tượng và mã tiền tố.",
            "Nút '+ Thêm vị trí mới': Khởi tạo khu vực mặt bằng mới để liên kết với tài sản trên cây thiết bị."
        ],
        "action_details": [
            {
                "name": "Thêm Phân Loại Thiết Bị & Danh Mục Mới",
                "location": "Góc trên bảng Danh mục phân loại hoặc bảng Vị trí của trang /portal/asset-categories/.",
                "trigger_workflow": "Mở modal nhập tên danh mục phân loại máy móc hoặc tên khu vực phân xưởng mới.",
                "permission": "asset_category:read và quyền ghi quản trị",
                "form_fields": [
                    "Tên phân loại / danh mục (*bắt buộc): Nhóm thiết bị (VD: Động cơ điện, Bơm ly tâm, Máy tiện CNC).",
                    "Mã tiền tố định danh (Code prefix): Tiền tố sinh mã tài sản (VD: MOT, PUMP, CNC).",
                    "Gán vị trí cha trên cây phân cấp không gian địa lý."
                ],
                "notes": "Phân loại khởi tạo sẽ hiển thị trên cây cấu trúc để gán máy móc và vật tư.",
                "action_triggers": [
                    "nút thêm danh mục tài sản ở đâu",
                    "chỗ nào bấm nút thêm phân loại thiết bị",
                    "chỉ tôi thêm phân loại thiết bị",
                    "nút thêm phân loại thiết bị ở đâu",
                    "cách tạo khu vực phân xưởng mới",
                    "chỉ tôi thêm vị trí mặt bằng",
                    "hướng dẫn cấu hình danh mục máy"
                ]
            }
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
            "cấu hình múi giờ và tiền tệ",
            "menu cài đặt ở đâu"
        ],
        "summary": "Cài đặt tham số vận hành của đơn vị/tenant: Nhận diện thương hiệu, giao diện, múi giờ và cấu hình thông báo.",
        "features": [
            "Thông tin doanh nghiệp: Tên đơn vị, Mã định danh tenant, Địa chỉ nhà máy, Mã số thuế.",
            "Nhận diện thương hiệu: Tải lên Logo xưởng, chọn bảng màu giao diện chủ đạo (Cyan, Emerald, Navy, Indigo, Amber).",
            "Cấu hình khu vực: Múi giờ xưởng (Asia/Ho_Chi_Minh), đơn vị tiền tệ mặc định (VND, USD).",
            "Cấu hình thông báo: Bật/tắt thông báo sự cố qua Email hoặc Webhook."
        ],
        "actions": [
            "Nút 'Lưu thay đổi': Áp dụng cấu hình giao diện và thông tin đơn vị ngay tức thì.",
            "Nút 'Tải lên Logo': Chọn tệp ảnh logo thương hiệu từ máy tính để hiển thị trên góc Header."
        ],
        "action_details": [
            {
                "name": "Tải Lên Logo & Lưu Cài Đặt Đơn Vị",
                "location": "Màn hình Cài Đặt Đơn Vị (/portal/settings/).",
                "trigger_workflow": "Cập nhật logo thương hiệu doanh nghiệp và lưu các thiết lập tham số hệ thống.",
                "permission": "tenant:update hoặc Quản trị viên",
                "form_fields": [
                    "Tải lên tệp Logo: Chọn file ảnh PNG/JPG logo nhà máy từ máy tính để hiển thị trên Header.",
                    "Bảng màu giao diện chủ đạo: Chọn bảng màu (Indigo, Emerald, Cyan, Amber).",
                    "Múi giờ hệ thống: Múi giờ xưởng (mặc định Asia/Ho_Chi_Minh).",
                    "Nút 'Lưu thay đổi': Áp dụng cài đặt cho toàn bộ người dùng trong đơn vị."
                ],
                "notes": "Thay đổi màu sắc và logo có hiệu lực ngay lập tức mà không cần khởi động lại máy chủ.",
                "action_triggers": [
                    "đổi logo xưởng và màu giao diện hệ thống làm thế nào",
                    "đổi logo thương hiệu bấm nút nào",
                    "chỉ tôi đổi logo thương hiệu công ty",
                    "nút đổi logo công ty ở đâu",
                    "cách dùng nút tải lên logo",
                    "làm sao để đổi màu giao diện hệ thống",
                    "làm sao đổi logo thương hiệu",
                    "hướng dẫn lưu cài đặt đơn vị"
                ]
            }
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
            "thư viện tài liệu kỹ thuật",
            "menu tri thức ai ở đâu"
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
        ],
        "action_details": [
            {
                "name": "Thêm Q&A Mẫu (Tri Thức Vàng)",
                "location": "Góc trên bên phải Header trang Quản Trị Tri Thức AI (/admin/rag-knowledge/), nút 'Thêm Q&A Mẫu'.",
                "trigger_workflow": "Mở popup modal 'Thêm Tri Thức Hỏi Đáp Mới' (#modal-add-qa).",
                "permission": "assistant:manage_knowledge hoặc Kỹ sư trưởng",
                "form_fields": [
                    "Phân loại tri thức: Bảo trì Thiết bị (EQUIPMENT_MAINTENANCE) hoặc Hướng dẫn Phần mềm (SYSTEM_FEATURE_GUIDE).",
                    "Áp dụng cho Model máy (nếu là thiết bị): Nhập mã model tương thích (VD: PUMP-X100).",
                    "Câu hỏi mẫu (*bắt buộc): Câu hỏi chuẩn mực kỹ thuật viên hay gặp.",
                    "Câu trả lời chuẩn (*bắt buộc): Hướng dẫn khắc phục chi tiết kèm quy trình an toàn bắt buộc."
                ],
                "notes": "Sau khi lưu, hệ thống lập tức vector hóa vào PGVector để Trợ lý AI phản hồi ngay cho kỹ thuật viên.",
                "action_triggers": [
                    "chỉ tôi sử dụng nút thêm tri thức mới",
                    "nút thêm q&a mẫu ở đâu",
                    "cách dùng nút thêm tri thức vàng",
                    "làm sao để thêm q&a mẫu",
                    "form thêm tri thức ai điền gì",
                    "ai có quyền thêm tri thức mẫu",
                    "hướng dẫn tạo tri thức vàng"
                ]
            },
            {
                "name": "Duyệt Tri Thức (Approve) Từ Hàng Đợi",
                "location": "Tab 2 (Hàng Đợi Thẩm Định) trang Quản Trị Tri Thức AI, nút màu xanh lá trên từng đề xuất mẹo bảo trì.",
                "trigger_workflow": "Kỹ sư trưởng phê duyệt một giải pháp sửa chữa thực tế từ phiếu bảo trì đã hoàn tất thành Tri thức Vàng.",
                "permission": "assistant:manage_knowledge (Kỹ sư trưởng)",
                "form_fields": [
                    "Chỉnh sửa câu trả lời chuẩn (Curated Answer, *bắt buộc): Chuẩn hóa câu chữ, bổ sung cảnh báo an toàn kỹ thuật.",
                    "Áp dụng cho Model máy: Chọn model thiết bị áp dụng mẹo sửa chữa này.",
                    "Nút 'Duyệt & Lưu Thành Tri Thức Vàng': Vector hóa vào PGVector và lưu vào thư viện tri thức vàng."
                ],
                "notes": "Tri thức sau khi duyệt sẽ trở thành câu trả lời chính thức của Trợ lý AI khi kỹ thuật viên khác gặp sự cố tương tự.",
                "action_triggers": [
                    "ai có quyền duyệt tri thức vàng trong hàng đợi",
                    "ai có quyền duyệt tri thức vàng",
                    "chỉ tôi duyệt tri thức hàng đợi thẩm định",
                    "nút duyệt tri thức ở đâu",
                    "cách dùng nút approve tri thức",
                    "cách duyệt hàng đợi thẩm định",
                    "chỉ tôi duyệt mẹo bảo trì",
                    "hướng dẫn duyệt mẹo bảo trì trong hàng đợi"
                ]
            },
            {
                "name": "Tải Lên Tài Liệu Kỹ Thuật PDF",
                "location": "Tab 3 (Thư Viện Tài Liệu) trang Quản Trị Tri Thức AI, nút 'Tải lên tài liệu mới'.",
                "trigger_workflow": "Mở modal tải file PDF sổ tay OEM hoặc quy trình kỹ thuật để AI bóc tách phân đoạn.",
                "permission": "assistant:manage_knowledge",
                "form_fields": [
                    "Tiêu đề tài liệu (*bắt buộc): Tên sổ tay vận hành hoặc cẩm nang bảo trì thiết bị.",
                    "Danh mục tài liệu: Sổ tay hãng (OEM_MANUAL) hoặc Hướng dẫn phần mềm (SYSTEM_SOFTWARE_GUIDE).",
                    "Model thiết bị áp dụng: Model máy tương ứng với cuốn sổ tay kỹ thuật.",
                    "Tệp tin đính kèm: Chọn file PDF từ máy tính để hệ thống bóc tách Parent-Child chunks và vector hóa."
                ],
                "notes": "Hỗ trợ trích xuất thông minh cả sơ đồ mạch và ảnh mặt cắt kỹ thuật đính kèm.",
                "action_triggers": [
                    "tải lên tài liệu kỹ thuật pdf vào trợ lý ai ở chỗ nào",
                    "chỉ tôi tải lên tài liệu kỹ thuật mới",
                    "nút tải lên tài liệu kỹ thuật ở đâu",
                    "nút tải lên tài liệu ở đâu",
                    "cách dùng nút upload tài liệu pdf",
                    "cách upload file pdf tài liệu",
                    "làm sao để nạp tài liệu vào ai",
                    "hướng dẫn tải lên sổ tay vận hành"
                ]
            }
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
            "theo dõi ai đã sửa dữ liệu",
            "menu audit logs ở đâu"
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
        ],
        "action_details": [
            {
                "name": "Xuất Nhật Ký Kiểm Toán",
                "location": "Thanh công cụ lọc của trang Nhật Ký Hệ Thống (/portal/audit-logs/).",
                "trigger_workflow": "Xuất file lịch sử thao tác người dùng (đăng nhập, sửa, xóa, đổi trạng thái) ra tệp dữ liệu.",
                "permission": "audit_logs:read",
                "form_fields": [
                    "Tự động xuất tệp dựa trên bộ lọc tài khoản và khoảng thời gian đã chọn."
                ],
                "notes": "Dữ liệu phục vụ công tác thanh tra bảo mật và kiểm toán an ninh thông tin.",
                "action_triggers": [
                    "chỉ tôi xuất nhật ký kiểm toán",
                    "nút xuất nhật ký ở đâu",
                    "nút xuất nhật ký kiểm toán ở đâu",
                    "cách dùng nút xuất audit logs",
                    "làm sao để tải file nhật ký hệ thống",
                    "cách tải file audit logs"
                ]
            }
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
            "quản trị đa đơn vị doanh nghiệp",
            "menu quản lý đơn vị ở đâu"
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
        ],
        "action_details": [
            {
                "name": "Khởi Tạo Đơn Vị Mới",
                "location": "Góc trên bên phải trang Quản Lý Đơn Vị (/portal/tenants/).",
                "trigger_workflow": "Mở modal đăng ký công ty/nhà máy mới vào hệ thống EAM đa đơn vị.",
                "permission": "Chỉ dành cho Superadmin hệ thống thuộc tenant SYSTEM (system:admin)",
                "form_fields": [
                    "Tên đơn vị / Nhà máy (*bắt buộc): Tên pháp nhân công ty thành viên.",
                    "Mã định danh tenant (*bắt buộc): Mã viết tắt không dấu (VD: FACTORY-02, STEEL-PLANT).",
                    "Hạn mức tài nguyên Quota: Số lượng máy móc tối đa, dung lượng lưu trữ tài liệu."
                ],
                "notes": "Hệ thống tự động thiết lập schema cơ sở dữ liệu riêng biệt đảm bảo an toàn đa người thuê.",
                "action_triggers": [
                    "chỉ tôi khởi tạo đơn vị mới",
                    "nút tạo tenant mới ở đâu",
                    "nút khởi tạo đơn vị mới ở đâu",
                    "cách dùng nút khởi tạo đơn vị mới",
                    "cách tạo tenant mới",
                    "làm sao để thêm công ty thành viên mới"
                ]
            }
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


def generate_action_guide_markdown(mod: Dict[str, Any], act: Dict[str, Any]) -> str:
    """Formats detailed action button metadata into a structured, crystal-clear guide section."""
    lines = [
        "### ℹ️ HƯỚNG DẪN TÍNH NĂNG HỆ THỐNG EAM:",
        f"#### Hướng dẫn thao tác: Nút \"{act['name']}\" ({act['name'].upper()})",
        f"- **Màn hình giao diện**: {mod['title']} (URL: `{mod['route_url']}`)",
        f"- **Vị trí nút bấm trên giao diện**: {act['location']}",
        f"- **Quy trình kích hoạt khi bấm**: {act['trigger_workflow']}",
        f"- **Điều kiện quyền hạn cần có (RBAC)**: {act['permission']}",
        "",
        "### 📝 Chi Tiết Biểu Mẫu / Các Trường Cần Điền:"
    ]
    if act.get('form_fields'):
        for field in act['form_fields']:
            lines.append(f"  • {field}")
    else:
        lines.append("  • Thao tác kích hoạt trực tiếp, không yêu cầu điền biểu mẫu phức tạp.")

    if act.get('notes'):
        lines.append("")
        lines.append(f"### 💡 Lưu ý vận hành: {act['notes']}")
        
    return "\n".join(lines)


def generate_dynamic_action_triggers(act: Dict[str, Any], mod: Dict[str, Any]) -> List[str]:
    """
    Dynamically generates a comprehensive, diverse set of trigger phrases for an action button.
    Includes colloquial, dialectal, form-field, permission, and location query variations.
    """
    raw_name = act.get('name', '')
    clean_aliases: List[str] = [raw_name.lower()]
    
    if '(' in raw_name and ')' in raw_name:
        main_part = raw_name.split('(')[0].strip().lower()
        sub_part = raw_name.split('(')[1].split(')')[0].strip().lower()
        if main_part and main_part not in clean_aliases:
            clean_aliases.append(main_part)
        if sub_part and sub_part not in clean_aliases:
            clean_aliases.append(sub_part)

    cleaned_aliases_extra = []
    for a in list(clean_aliases):
        if a.startswith('nút '):
            cleaned_aliases_extra.append(a[4:].strip())
        if 'vật tư' in a:
            cleaned_aliases_extra.append(a.replace('vật tư', 'phụ tùng'))
            cleaned_aliases_extra.append(a.replace('vật tư', 'linh kiện'))
        if 'phụ tùng' in a:
            cleaned_aliases_extra.append(a.replace('phụ tùng', 'vật tư'))
        if 'phiếu bảo trì' in a:
            cleaned_aliases_extra.append(a.replace('phiếu bảo trì', 'phiếu sửa chữa'))
            cleaned_aliases_extra.append(a.replace('phiếu bảo trì', 'phiếu wo'))
            cleaned_aliases_extra.append(a.replace('phiếu bảo trì', 'phiếu'))
        if 'tạo phiếu' in a:
            cleaned_aliases_extra.append(a.replace('tạo phiếu', 'lập phiếu'))
            cleaned_aliases_extra.append(a.replace('tạo phiếu', 'lập phiếu wo'))
        if 'hungarian' in a:
            cleaned_aliases_extra.extend(['điều phối 1-1', 'điều phối hungarian', 'điều phối 1-1 hungarian', 'ghép việc 1-1'])
        if 'genetic' in a or 'lập lịch cả ca' in a:
            cleaned_aliases_extra.extend(['lập lịch ca trực ga', 'lập lịch ga', 'xếp lịch ca trực ga', 'lập lịch cả ca'])
        if 'tsp' in a:
            cleaned_aliases_extra.extend(['tối ưu lộ trình di chuyển', 'tối ưu lộ trình tsp', 'lộ trình di chuyển'])
        if 'qr' in a:
            cleaned_aliases_extra.extend(['quét mã qr', 'quét qr code', 'quét qr', 'in tem qr'])
        if 'excel' in a or 'xuất' in a:
            cleaned_aliases_extra.extend(['xuất excel kho', 'xuất file kho', 'tải excel kho', 'xuất excel'])
        if 'kỹ năng' in a or 'chứng chỉ' in a:
            cleaned_aliases_extra.extend(['thêm kỹ năng cho thợ', 'thêm kỹ năng thợ', 'thêm kỹ năng', 'thêm chứng chỉ', 'kỹ năng cho thợ'])
        if 'phân loại' in a or 'danh mục' in a:
            cleaned_aliases_extra.extend(['thêm phân loại thiết bị', 'thêm phân loại', 'phân loại thiết bị', 'thêm danh mục thiết bị', 'danh mục thiết bị', 'thêm danh mục'])

    for ea in cleaned_aliases_extra:
        if ea and ea not in clean_aliases:
            clean_aliases.append(ea)

    triggers = set()

    # 1. Include explicit action_triggers from metadata
    for t in act.get('action_triggers', []):
        triggers.add(t.strip().lower())

    # 2. Dynamic template expansions for every alias
    for alias in clean_aliases:
        alias = alias.strip()
        if not alias:
            continue
        triggers.add(f"chỉ tôi sử dụng nút {alias} đi")
        triggers.add(f"chỉ tôi sử dụng nút {alias}")
        triggers.add(f"chỉ tôi dùng nút {alias}")
        triggers.add(f"chỉ tôi nút {alias}")
        triggers.add(f"chỉ mình dùng nút {alias}")
        triggers.add(f"chỉ em cách bấm nút {alias}")
        triggers.add(f"chỉ cách {alias}")
        triggers.add(f"bày tôi dùng nút {alias}")
        triggers.add(f"bày tôi sử dụng nút {alias}")
        triggers.add(f"bày cách bấm nút {alias}")
        triggers.add(f"làm sao để bấm nút {alias}")
        triggers.add(f"làm sao để {alias}")
        triggers.add(f"làm thế nào để {alias}")
        triggers.add(f"cách dùng nút {alias}")
        triggers.add(f"cách bấm nút {alias}")
        triggers.add(f"hướng dẫn thao tác {alias}")
        triggers.add(f"hướng dẫn bấm nút {alias}")
        triggers.add(f"nút {alias} ở đâu")
        triggers.add(f"nút {alias} nằm ở đâu")
        triggers.add(f"nút {alias} bấm ở đâu")
        triggers.add(f"nút {alias} bấm ở mô")
        triggers.add(f"nút {alias} ở chỗ nào")
        triggers.add(f"cho hỏi nút {alias} ở đâu")
        triggers.add(f"vị trí nút {alias} ở đâu")
        triggers.add(f"chỗ bấm nút {alias}")
        triggers.add(f"bấm đâu để {alias}")
        triggers.add(f"ấn đâu để {alias}")
        triggers.add(f"nút {alias} cần quyền gì")
        triggers.add(f"ai có quyền bấm nút {alias}")
        triggers.add(f"ai được bấm nút {alias}")
        triggers.add(f"form {alias} điền gì")
        triggers.add(f"biểu mẫu {alias} điền gì")
        triggers.add(f"các trường trong form {alias}")
        triggers.add(f"ý nghĩa các ô trong form {alias}")
        triggers.add(f"form {alias} gồm những ô nào")

    # 3. Contextual operational phrases for specific action types
    name_clean = raw_name.lower()
    if 'tạo phiếu' in name_clean or 'lập phiếu' in name_clean:
        triggers.add("máy bơm bị xì nhớt thì bấm nút tạo phiếu ở đâu")
        triggers.add("máy bơm bị rỉ nhớt muốn lập phiếu wo thì ấn nút nào")
        triggers.add("máy bị hỏng thì bấm nút tạo phiếu ở đâu")
        triggers.add("máy gặp sự cố thì bấm nút tạo phiếu ở đâu")
        triggers.add("khi máy hỏng thì ấn nút nào tạo phiếu")
        triggers.add("báo sự cố máy móc ấn nút nào")
        triggers.add("báo hỏng thiết bị lập phiếu ở đâu")
        triggers.add("bấm nút tạo phiếu ở đâu")
        triggers.add("nút tạo phiếu ở đâu")
        triggers.add("tạo phiếu bảo trì máy bơm")
        triggers.add("làm sao để tạo phiếu bảo trì máy bơm")

    if 'vật tư' in name_clean or 'phụ tùng' in name_clean:
        triggers.add("thêm phụ tùng mới vào kho bấm đâu")
        triggers.add("nhập phụ tùng mới vào kho bấm đâu")
        triggers.add("thêm vật tư mới vào kho bấm đâu")
        triggers.add("thêm phụ tùng vào kho")
        triggers.add("thêm vật tư vào kho")
        triggers.add("chỉ tôi nút thêm vật tư")
        triggers.add("chỉ tôi dùng nút thêm vật tư")
        triggers.add("hướng dẫn bấm nút min-stock kho")

    if 'excel' in name_clean or 'xuất' in name_clean:
        triggers.add("nút xuất excel trên kho bấm ở mô")
        triggers.add("làm sao để xuất excel kho")
        triggers.add("xuất excel kho ở đâu")
        triggers.add("tải excel tồn kho ở đâu")

    if 'hungarian' in name_clean or 'điều phối' in name_clean:
        triggers.add("khi nào thì bấm nút 1-1 hungarian")
        triggers.add("nút điều phối 1-1 hungarian bấm ở đâu")
        triggers.add("nút giao việc 1-1 bấm ở đâu")

    if 'quét' in name_clean or 'qr' in name_clean:
        triggers.add("nút quét mã qr nằm ở mô")
        triggers.add("quét mã qr bấm ở đâu")
        triggers.add("quét qr code bấm ở đâu")

    return sorted(list(triggers))


def scan_and_index_system_knowledge() -> Dict[str, Any]:
    """
    Executes automated codebase scan of portal modules, generates clean Parent-Child chunks,
    vectorizes them into PGVector, and registers corresponding Curated QA entries.
    All system knowledge chunks are stored globally (tenant_id=NULL, is_system_guide=TRUE).
    Optimized with batch vectorization for maximum performance.
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

    items_to_index: List[Dict[str, Any]] = []
    qa_to_create: List[Dict[str, Any]] = []

    # Iterate over all portal modules
    for page_idx, mod in enumerate(PORTAL_MODULES_METADATA, start=1):
        guide_md = generate_module_guide_markdown(mod)
        section_title = mod['title']

        # 1. Module-level child chunks
        for trig in mod['triggers']:
            clean_trig = trig.strip().lower()
            items_to_index.append({
                "section_title": section_title,
                "content": clean_trig,
                "parent_content": guide_md,
                "page_number": page_idx
            })

        # Register primary module Q&A
        primary_question = mod['triggers'][0]
        qa_to_create.append({
            "question_pattern": primary_question,
            "gold_answer": guide_md
        })

        # 2. Detailed action buttons deep child chunks
        for act in mod.get('action_details', []):
            act_md = generate_action_guide_markdown(mod, act)
            act_title = f"Nút {act['name']} - {mod['title']}"
            
            # Action triggers dynamically generated
            dynamic_triggers = generate_dynamic_action_triggers(act, mod)
            for act_trig in dynamic_triggers:
                clean_act_trig = act_trig.strip().lower()
                items_to_index.append({
                    "section_title": act_title,
                    "content": clean_act_trig,
                    "parent_content": act_md,
                    "page_number": page_idx
                })

            # Action semantic summary chunk
            summary_chunk = (
                f"Thao tác nút {act['name']} ({mod['title']}): "
                f"Vị trí: {act['location']}. "
                f"Quy trình: {act['trigger_workflow']}. "
                f"Quyền hạn yêu cầu: {act['permission']}."
            )
            items_to_index.append({
                "section_title": act_title,
                "content": summary_chunk.lower(),
                "parent_content": act_md,
                "page_number": page_idx
            })

            # Form fields individual chunks
            for fld in act.get('form_fields', []):
                clean_fld = fld.strip()
                items_to_index.append({
                    "section_title": act_title,
                    "content": f"trường {clean_fld.lower()} trong biểu mẫu form nút {act['name'].lower()}",
                    "parent_content": act_md,
                    "page_number": page_idx
                })
                items_to_index.append({
                    "section_title": act_title,
                    "content": f"hướng dẫn điền và ý nghĩa {clean_fld.lower()} ({mod['title'].lower()})",
                    "parent_content": act_md,
                    "page_number": page_idx
                })
                if '(' in clean_fld:
                    label = clean_fld.split('(')[0].strip().lower()
                    if label:
                        items_to_index.append({
                            "section_title": act_title,
                            "content": f"trường {label} trong form {act['name'].lower()} là gì",
                            "parent_content": act_md,
                            "page_number": page_idx
                        })
                        items_to_index.append({
                            "section_title": act_title,
                            "content": f"ý nghĩa trường {label} trong form {act['name'].lower()}",
                            "parent_content": act_md,
                            "page_number": page_idx
                        })
                        items_to_index.append({
                            "section_title": act_title,
                            "content": f"trường {label} điền gì",
                            "parent_content": act_md,
                            "page_number": page_idx
                        })

            if dynamic_triggers:
                primary_act_trig = dynamic_triggers[0]
                qa_to_create.append({
                    "question_pattern": primary_act_trig,
                    "gold_answer": act_md
                })

    # Batch compute embeddings for all child chunk texts
    texts_to_embed = [item['content'] for item in items_to_index]
    logger.info("Computing embeddings for %d system guide chunk triggers...", len(texts_to_embed))
    vectors = embed_texts(texts_to_embed, batch_size=128)

    indexed_count = 0
    curated_count = 0

    with transaction.atomic():
        # Clean existing system guide chunks for doc
        DocumentChunk.all_objects.filter(document=doc).delete()

        # Bulk create DocumentChunk objects
        chunk_objs = [
            DocumentChunk(
                document=doc,
                tenant_id=None,
                is_system_guide=True,
                source_type='SYSTEM_GUIDE',
                section_title=item['section_title'],
                content=item['content'],
                parent_content=item['parent_content'],
                embedding=vec,
                page_number=item['page_number'],
                is_active=True
            )
            for item, vec in zip(items_to_index, vectors)
        ]
        DocumentChunk.objects.bulk_create(chunk_objs, batch_size=250)
        indexed_count = len(chunk_objs)

        # Register Curated Gold Q&As
        for qa_item in qa_to_create:
            CuratedQAKnowledge.all_objects.filter(
                question_pattern__iexact=qa_item['question_pattern']
            ).delete()

            CuratedQAKnowledge.objects.create(
                tenant_id=None,
                is_system_guide=True,
                category='SYSTEM_FEATURE',
                question_pattern=qa_item['question_pattern'],
                gold_answer=qa_item['gold_answer'],
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
