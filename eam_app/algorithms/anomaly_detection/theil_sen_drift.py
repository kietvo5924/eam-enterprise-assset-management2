from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Any
import numpy as np
try:
    from sklearn.linear_model import TheilSenRegressor
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    TheilSenRegressor = None

try:
    from scipy.stats import theilslopes
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    theilslopes = None


def _calculate_theil_sen_slope(x_days: np.ndarray, y_vals: np.ndarray) -> float:
    """Robust Theil-Sen slope calculation with Sklearn -> SciPy -> Pure NumPy fallback."""
    if HAS_SKLEARN and TheilSenRegressor is not None:
        reg = TheilSenRegressor(random_state=42).fit(x_days.reshape(-1, 1), y_vals)
        return float(reg.coef_[0])
    elif HAS_SCIPY and theilslopes is not None:
        res = theilslopes(y_vals, x_days)
        return float(res.slope if hasattr(res, 'slope') else res[0])
    else:
        # Pure NumPy pairwise slopes median
        n = len(x_days)
        slopes = []
        for i in range(n):
            for j in range(i + 1, n):
                dx = x_days[j] - x_days[i]
                if abs(dx) > 1e-7:
                    slopes.append((y_vals[j] - y_vals[i]) / dx)
        return float(np.median(slopes)) if slopes else 0.0


def compute_theil_sen_drift(
    timestamps: List[Any],
    values: List[float],
    limit_value: float = 7.1
) -> Tuple[Optional[float], Optional[int]]:
    """
    Cấp độ 3: Động cơ Theil-Sen Robust Trend Drift (Mục 11.1).
    Tuân thủ:
    - Quy Tắc 3: Hồi quy mạnh mẽ Theil-Sen miễn nhiễm 29% ngoại lai do trượt tay (TC-ANOM-03).
    - Quy Tắc 7: Trục thời gian tính theo số ngày thực tế trôi qua (Timestamp-Based Elapsed Days, TC-ANOM-07).
    
    timestamps: Danh sách các datetime hoặc timestamp thực tế
    values: Danh sách các giá trị đo đạc
    limit_value: Ngưỡng tới hạn (mặc định 7.1 mm/s theo ISO 10816 Zone D)
    
    Trả về:
    (slope, days_remaining)
    - slope: Tốc độ suy thoái mỗi ngày (đơn vị / ngày)
    - days_remaining: Số ngày dự kiến chạm ngưỡng nguy hiểm, hoặc None nếu không có xu hướng tăng
    """
    if len(values) < 5 or len(timestamps) != len(values):
        return None, None

    # Chuyển đổi timestamp sang datetime và lọc bỏ các giá trị không hợp lệ (tránh chèn now() làm sai lệch chuỗi thời gian)
    from django.utils import timezone as dj_timezone
    from datetime import timezone as dt_timezone
    valid_pairs = []
    for t, v in zip(timestamps, values):
        if v is None:
            continue
        try:
            val_f = float(v)
        except (ValueError, TypeError):
            continue

        dt = None
        if isinstance(t, datetime):
            dt = t if dj_timezone.is_aware(t) else dj_timezone.make_aware(t, dt_timezone.utc)
        elif hasattr(t, 'isoformat') and callable(getattr(t, 'isoformat')):
            dt = t if dj_timezone.is_aware(t) else dj_timezone.make_aware(t, dt_timezone.utc)
        elif isinstance(t, str):
            try:
                parsed = datetime.fromisoformat(t.replace('Z', '+00:00'))
                dt = parsed if dj_timezone.is_aware(parsed) else dj_timezone.make_aware(parsed, dt_timezone.utc)
            except Exception:
                # Bỏ qua mốc thời gian không hợp lệ, tuyệt đối không gán now() làm biến dạng độ dốc slope
                continue
        elif isinstance(t, (int, float)):
            try:
                dt = datetime.fromtimestamp(t, tz=dt_timezone.utc)
            except Exception:
                continue

        if dt is not None:
            valid_pairs.append((dt, val_f))

    if len(valid_pairs) < 3:
        return None, None

    # Sắp xếp theo trình tự thời gian tăng dần
    valid_pairs.sort(key=lambda item: item[0])
    dt_list = [c[0] for c in valid_pairs]
    sorted_values = [c[1] for c in valid_pairs]

    t0_ts = dt_list[0].timestamp()
    # Quy Tắc 7: Tính số ngày thực tế trôi qua (Elapsed Days) bằng Unix timestamp chống lỗi timezone
    x_days = np.array([(t.timestamp() - t0_ts) / 86400.0 for t in dt_list], dtype=float)
    y = np.array(sorted_values, dtype=float)

    # Quy Tắc 3: Hồi quy Theil-Sen miễn nhiễm ngoại lai (TC-ANOM-03)
    slope = _calculate_theil_sen_slope(x_days, y)

    current_val = float(sorted_values[-1])

    # Hỗ trợ cả 2 chiều suy thoái: Tăng (rung, nhiệt) và Giảm (áp suất dầu, lưu lượng, điện áp)
    if slope > 0.01:
        if current_val >= limit_value:
            return round(slope, 4), 0  # Đã chạm hoặc vượt ngưỡng
        days_remaining = int((limit_value - current_val) / slope)
        return round(slope, 4), max(1, days_remaining)
    elif slope < -0.01 and limit_value < current_val:
        # Xu hướng tụt giảm về ngưỡng tới hạn sàn
        days_remaining = int((current_val - limit_value) / abs(slope))
        return round(slope, 4), max(1, days_remaining)
    else:
        return round(slope, 4), None  # Không có xu hướng suy thoái đáng kể


def evaluate_trend_drift(
    timestamps: List[Any],
    values: List[float],
    limit_value: float = 7.1,
    current_time: Optional[datetime] = None,
    metric_code: Optional[str] = None
) -> dict:
    """
    Đánh giá chi tiết xu hướng suy thoái và dự phóng ngày chạm ngưỡng.
    Hỗ trợ ngưỡng slope linh hoạt theo từng loại chỉ số và kiểm soát độ tin cậy thời gian dài.
    """
    from django.utils import timezone as dj_timezone
    slope, days_remaining = compute_theil_sen_drift(timestamps, values, limit_value)

    now = current_time or (timestamps[-1] if timestamps and isinstance(timestamps[-1], datetime) else dj_timezone.now())

    # Ngưỡng nhạy cảm slope theo từng loại kênh đo
    metric_slope_thresholds = {
        'VIBRATION': 0.01,
        'TEMPERATURE': 0.1,
        'PRESSURE': 0.05,
        'CURRENT': 0.2,
        'VOLTAGE': 0.5,
        'RPM': 2.0,
        'FLOW_RATE': 0.5,
    }
    threshold_slope = metric_slope_thresholds.get(str(metric_code).upper(), 0.01) if metric_code else 0.01

    is_drifting = slope is not None and abs(slope) >= threshold_slope
    should_create_draft_pm = days_remaining is not None and days_remaining <= 7

    # Độ tin cậy dự báo: Nếu dự đoán > 365 ngày (1 năm), gắn cờ dự báo dài hạn thay vì ấn định ngày tuyệt đối
    is_long_term = days_remaining is not None and days_remaining > 365
    predicted_date = (now + timedelta(days=days_remaining)).strftime('%Y-%m-%d') if (days_remaining is not None and not is_long_term) else None

    return {
        "isDrifting": is_drifting,
        "slopePerDay": slope,
        "daysRemaining": days_remaining,
        "predictedFailureDate": predicted_date,
        "isLongTermProjection": is_long_term,
        "shouldTriggerDraftPM": should_create_draft_pm,
        "limitValue": limit_value
    }
