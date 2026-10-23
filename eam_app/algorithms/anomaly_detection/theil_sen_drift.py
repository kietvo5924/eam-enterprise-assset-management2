from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Any
import numpy as np
from sklearn.linear_model import TheilSenRegressor


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

    # Chuyển đổi timestamp sang datetime nếu cần
    dt_list = []
    for t in timestamps:
        if isinstance(t, datetime):
            dt_list.append(t)
        elif hasattr(t, 'isoformat'):
            dt_list.append(t)
        elif isinstance(t, str):
            try:
                dt_list.append(datetime.fromisoformat(t.replace('Z', '+00:00')))
            except Exception:
                dt_list.append(datetime.now())
        else:
            dt_list.append(datetime.now())

    t0 = dt_list[0]
    # Quy Tắc 7: Tính số ngày thực tế trôi qua (Elapsed Days)
    X = np.array([(t - t0).total_seconds() / 86400.0 for t in dt_list]).reshape(-1, 1)
    y = np.array(values, dtype=float)

    # Quy Tắc 3: Hồi quy Theil-Sen miễn nhiễm ngoại lai (TC-ANOM-03)
    reg = TheilSenRegressor(random_state=42).fit(X, y)
    slope = float(reg.coef_[0])  # Tốc độ suy thoái mỗi ngày

    if slope <= 0.01:
        return round(slope, 4), None  # Không có xu hướng tăng đáng kể

    current_val = float(values[-1])
    if current_val >= limit_value:
        return round(slope, 4), 0  # Đã chạm hoặc vượt ngưỡng

    days_remaining = int((limit_value - current_val) / slope)
    return round(slope, 4), max(1, days_remaining)


def evaluate_trend_drift(
    timestamps: List[Any],
    values: List[float],
    limit_value: float = 7.1,
    current_time: Optional[datetime] = None
) -> dict:
    """
    Đánh giá chi tiết xu hướng suy thoái và dự phóng ngày chạm ngưỡng.
    """
    slope, days_remaining = compute_theil_sen_drift(timestamps, values, limit_value)
    
    now = current_time or (timestamps[-1] if timestamps and isinstance(timestamps[-1], datetime) else datetime.now())
    predicted_date = (now + timedelta(days=days_remaining)).strftime('%Y-%m-%d') if days_remaining is not None else None

    is_drifting = slope is not None and slope > 0.01
    should_create_draft_pm = days_remaining is not None and days_remaining <= 7

    return {
        "isDrifting": is_drifting,
        "slopePerDay": slope,
        "daysRemaining": days_remaining,
        "predictedFailureDate": predicted_date,
        "shouldTriggerDraftPM": should_create_draft_pm,
        "limitValue": limit_value
    }
