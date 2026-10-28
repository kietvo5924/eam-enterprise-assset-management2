"""
Hằng số và siêu tham số cho Module Dự báo Chi phí & Ngân sách Bảo trì (Task 11.6).
"""
from decimal import Decimal

# Hyperparameters for Quantile Regression Forests (Rule 9 & QRF Spec)
QRF_N_ESTIMATORS = 100
QRF_MAX_DEPTH = 6
QRF_MIN_SAMPLES_SPLIT = 4
QRF_MIN_SAMPLES_LEAF = 2
RANDOM_STATE = 42

# Default Economic and Safety Rates (Rule 4 & Rule 8)
DEFAULT_INFLATION_RATE = 0.045               # 4.5% lạm phát vật tư hàng năm
DEFAULT_CONTINGENCY_BUFFER_RATE = 0.05       # 5.0% quỹ dự phòng khẩn cấp
DEFAULT_LABOR_HOURLY_RATE = Decimal('150000.00') # 150,000 VNĐ / giờ công chuẩn

# Budget Overrun Thresholds (Rule 11)
WARNING_BUDGET_USAGE_RATIO = 85.0            # >= 85% -> Trạng thái WARNING
CRITICAL_BUDGET_USAGE_RATIO = 100.0          # >= 100% -> Trạng thái CRITICAL_OVERRUN

# Pareto 80/20 & RRR Lemon Asset Audit Thresholds (Rule 7)
LEMON_ASSET_COST_CONCENTRATION_THRESHOLD = 0.50  # >= 50% chi phí
LEMON_ASSET_PERCENT_THRESHOLD = 0.05             # <= 5% số lượng thiết bị
RRR_BAD_ACTOR_THRESHOLD = 70.0                   # RRR >= 70% nguyên giá -> Bad Actor

# Training Requirements & Cold Start (Rule 12)
MIN_MONTHS_TRAINING_DATA = 3                 # Tối thiểu 3 tháng dữ liệu để kích hoạt AI

# 16 Multivariate Time-Series Features (Section 4.1)
FEATURE_NAMES = [
    "net_cost_lag_1",             # 1. Chi phí ròng kỳ trễ 1
    "net_cost_lag_2",             # 2. Chi phí ròng kỳ trễ 2
    "net_cost_lag_3",             # 3. Chi phí ròng kỳ trễ 3
    "sma_3_cost",                 # 4. Trung bình trượt chi phí 3 tháng
    "sma_6_cost",                 # 5. Trung bình trượt chi phí 6 tháng
    "rolling_std_3",              # 6. Độ biến động chi phí trượt 3 tháng
    "backlog_orders_count",       # 7. Số lượng Work Order tồn đọng quá hạn
    "deferred_maintenance_hours", # 8. Tổng số giờ bảo dưỡng bị hoãn lại
    "active_assets_count",        # 9. Tổng số lượng thiết bị đang hoạt động
    "avg_asset_age_years",        # 10. Độ tuổi trung bình dàn máy móc
    "breakdown_cm_ratio",         # 11. Tỷ lệ sự cố đột xuất
    "rul_critical_liability",     # 12. Nghĩa vụ tài chính phụ tùng máy RUL Critical (11.5)
    "total_fleet_rav",            # 13. Tổng giá trị thay thế toàn bộ dàn máy (RAV)
    "class_a_cost_ratio",         # 14. Tỷ trọng chi phí thuộc nhóm thiết bị Class A / Bad Actors
    "seasonality_month",          # 15. Hệ số mùa vụ (Tháng 1 - 12)
    "working_days_in_month",      # 16. Số ngày làm việc thực tế trong tháng
]

