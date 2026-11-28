"""
The 10 Core Defense Guardrails for Predictive Maintenance RUL (Phase 11.5).
Phòng vệ toàn diện: Khởi động nguội, Lọc Standby, Kẹp Phantom Recovery, Lọc đơn điệu vật lý,
Độ bất định MC-Dropout, Ngưỡng động Lead-time, Suy thoái đột biến, Phân luồng tài sản tĩnh.
"""

import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from .constants import (
    COLD_START_MIN_SAMPLES, MC_DROPOUT_PASSES, Z_SCORE_90_PERCENT,
    HIGH_UNCERTAINTY_STD_THRESHOLD, MONOTONIC_NOISE_EPSILON,
    PHANTOM_RECOVERY_JUMP_RATIO, RAPID_DEGRADATION_RATE_THRESHOLD,
    RAPID_DEGRADATION_PERCENT_THRESHOLD, LEAD_TIME_SAFETY_BUFFER_DAYS,
    MIN_CRITICAL_THRESHOLD_DAYS
)


class PredictiveRULGuardrails:
    """Bộ 10 Quy Tắc Phòng Vệ Công Nghiệp."""

    @staticmethod
    def validate_asset_machinery_type(asset) -> Tuple[bool, Optional[str]]:
        """
        Quy Tắc 10: Phân Luồng Thiết Bị Cơ Điện vs Tài Sản Tĩnh.
        Chặn thực thi đối với các tài sản tĩnh (bàn, ghế, tủ văn phòng).
        """
        # 1. Kiểm tra thuộc tính tường minh asset_type do người dùng chọn
        asset_type = getattr(asset, 'asset_type', None)
        if asset_type == 'STATIC':
            return False, (
                f"Tài sản tĩnh '{asset.name}' không đo đạc rung nhiệt; "
                f"tuổi thọ được quản lý qua Khấu hao đường thẳng tại Phân hệ 10.3."
            )
        if asset_type == 'MACHINERY':
            return True, None

        # 2. Bắt buộc tài sản phải được chỉ định loại rõ ràng
        return False, (
            f"Tài sản '{asset.name}' chưa được chỉ định loại tài sản hợp lệ. "
            f"Vui lòng cập nhật loại tài sản (Thiết bị cơ điện, máy móc hoặc Tài sản tĩnh)."
        )

    @staticmethod
    def filter_running_meter_readings(readings_qs) -> List[Dict[str, Any]]:
        """
        Quy Tắc 3: Lọc Bỏ Trạng Thái Nghỉ (IDLE / STANDBY / WARM_UP) và gom nhóm đa kênh theo từng chu kỳ đo.
        - Nếu các bản ghi có cùng round_id: gộp thành một chu kỳ đo đa kênh duy nhất.
        - Nếu round_id trống (ví dụ IoTSensorAlertView lưu TEMPERATURE và VIBRATION cùng mốc thời gian):
          gộp các bản ghi liên tiếp trong cửa sổ <= 2 giây nếu không trùng kênh cảm biến đã có.
        - Tuyệt đối không gán cứng vibration=0.0 cho dòng nhiệt độ đơn lẻ làm phồng số mẫu và sai lệch dữ liệu.
        """
        def _canonical_channel(metric_code: str) -> Optional[str]:
            mc = str(metric_code or '').upper().strip()
            if mc == 'VIBRATION':
                return 'vibration'
            if mc in ('TEMPERATURE', 'BEARING_TEMP'):
                return 'temperature'
            if mc == 'PRESSURE':
                return 'pressure'
            if mc == 'LOAD_FACTOR':
                return 'load_factor'
            return None

        eligible_rows = []
        for r in readings_qs:
            state = str(getattr(r, 'machine_state', 'RUNNING') or 'RUNNING').upper().strip()
            is_pre = getattr(r, 'is_pre_repair', False)
            is_supp = getattr(r, 'is_suppressed', False)
            if state == 'RUNNING' and not is_pre and not is_supp:
                eligible_rows.append(r)

        # Đảm bảo thứ tự thời gian trước khi gom nhóm
        eligible_rows.sort(key=lambda x: (getattr(x, 'reading_date', None), str(getattr(x, 'id', ''))))

        grouped_by_key: Dict[str, Dict[str, Any]] = {}
        ordered_keys: List[str] = []
        open_nonround_key: Optional[str] = None
        open_nonround_ts = None
        anon_seq = 0

        for r in eligible_rows:
            channel = _canonical_channel(getattr(r, 'metric_code', ''))
            r_date = getattr(r, 'reading_date', None)
            round_id = getattr(r, 'round_id', None)

            if round_id:
                group_key = f"round:{round_id}"
            else:
                can_merge = False
                if (
                    open_nonround_key is not None
                    and open_nonround_ts is not None
                    and r_date is not None
                    and channel is not None
                    and channel not in grouped_by_key[open_nonround_key]['channels_observed']
                ):
                    delta_sec = abs((r_date - open_nonround_ts).total_seconds())
                    if delta_sec <= 2.0:
                        can_merge = True

                if can_merge:
                    group_key = open_nonround_key
                else:
                    anon_seq += 1
                    group_key = f"ts:{anon_seq}"
                    open_nonround_key = group_key
                    open_nonround_ts = r_date

            if group_key not in grouped_by_key:
                grouped_by_key[group_key] = {
                    'id': str(r.id),
                    'reading_ids': [],
                    'round_id': str(round_id) if round_id else None,
                    'reading_date': r_date,
                    'vibration': None,
                    'temperature': None,
                    'ambient_temperature': None,
                    'pressure': None,
                    'load_factor': None,
                    'machine_state': 'RUNNING',
                    'channels_observed': [],
                }
                ordered_keys.append(group_key)

            bucket = grouped_by_key[group_key]
            bucket['reading_ids'].append(str(r.id))
            val_f = float(r.reading_value) if getattr(r, 'reading_value', None) is not None else None

            if channel == 'vibration' and val_f is not None:
                bucket['vibration'] = val_f
                if 'vibration' not in bucket['channels_observed']:
                    bucket['channels_observed'].append('vibration')
            elif channel == 'temperature' and val_f is not None:
                bucket['temperature'] = val_f
                if 'temperature' not in bucket['channels_observed']:
                    bucket['channels_observed'].append('temperature')
            elif channel == 'pressure' and val_f is not None:
                bucket['pressure'] = val_f
                if 'pressure' not in bucket['channels_observed']:
                    bucket['channels_observed'].append('pressure')
            elif channel == 'load_factor' and val_f is not None:
                bucket['load_factor'] = val_f
                if 'load_factor' not in bucket['channels_observed']:
                    bucket['channels_observed'].append('load_factor')

            amb = getattr(r, 'ambient_temperature', None)
            if amb is not None and bucket['ambient_temperature'] is None:
                bucket['ambient_temperature'] = float(amb)

            lf = getattr(r, 'load_factor', None)
            if lf is not None and bucket['load_factor'] is None:
                bucket['load_factor'] = float(lf)

        valid_cycles = []
        for k in ordered_keys:
            b = grouped_by_key[k]
            if b['load_factor'] is None:
                b['load_factor'] = 1.0
            # Chỉ tính chu kỳ có ít nhất 1 kênh đo cảm biến chính
            if (b['vibration'] is not None) or (b['temperature'] is not None) or (b['pressure'] is not None):
                b['metric_code'] = '+'.join(c.upper() for c in b['channels_observed']) if b['channels_observed'] else 'UNKNOWN'
                valid_cycles.append(b)
        return valid_cycles

    @staticmethod
    def analyze_grouped_channel_completeness(
        grouped_cycles: List[Dict[str, Any]],
        raw_running_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """Thống kê độ đầy đủ đa kênh thực tế trên các chu kỳ đo đã gom nhóm."""
        n_cycles = len(grouped_cycles)
        vib_cnt = sum(1 for c in grouped_cycles if c.get('vibration') is not None)
        temp_cnt = sum(1 for c in grouped_cycles if (c.get('temperature') is not None or c.get('bearing_temperature') is not None))
        amb_cnt = sum(1 for c in grouped_cycles if c.get('ambient_temperature') is not None)
        press_cnt = sum(1 for c in grouped_cycles if c.get('pressure') is not None)
        load_cnt = sum(1 for c in grouped_cycles if c.get('load_factor') is not None)

        observed_channels = []
        missing_channels = []
        if vib_cnt > 0:
            observed_channels.append('VIBRATION')
        else:
            missing_channels.append('VIBRATION')

        if temp_cnt > 0:
            observed_channels.append('TEMPERATURE')
        else:
            missing_channels.append('TEMPERATURE')

        if amb_cnt > 0:
            observed_channels.append('AMBIENT_TEMPERATURE')
        else:
            missing_channels.append('AMBIENT_TEMPERATURE')

        if press_cnt > 0:
            observed_channels.append('PRESSURE')
        else:
            missing_channels.append('PRESSURE')

        core_slots = n_cycles * 3  # vibration, temperature, pressure
        core_filled = vib_cnt + temp_cnt + press_cnt
        completeness_ratio = round(float(core_filled) / core_slots, 3) if core_slots > 0 else 0.0

        channel_labels_vi = {
            'VIBRATION': 'Độ rung RMS',
            'TEMPERATURE': 'Nhiệt độ ổ trục/máy',
            'AMBIENT_TEMPERATURE': 'Nhiệt độ môi trường',
            'PRESSURE': 'Áp suất',
        }
        obs_vi = [channel_labels_vi[c] for c in observed_channels]
        miss_vi = [channel_labels_vi[c] for c in missing_channels]
        summary = f"Gom {n_cycles} chu kỳ đo RUNNING"
        if raw_running_count is not None:
            summary += f" (từ {raw_running_count} bản ghi cảm biến)"
        if obs_vi:
            summary += f". Kênh có dữ liệu: {', '.join(obs_vi)}"
        if miss_vi:
            summary += f". Kênh chưa có dữ liệu: {', '.join(miss_vi)} (áp dụng giá trị trung tính, không suy đoán quá nhiệt)"

        return {
            'groupedCyclesCount': n_cycles,
            'rawReadingsCount': raw_running_count if raw_running_count is not None else n_cycles,
            'cyclesWithVibration': vib_cnt,
            'cyclesWithTemperature': temp_cnt,
            'cyclesWithAmbientTemperature': amb_cnt,
            'cyclesWithPressure': press_cnt,
            'cyclesWithLoadFactor': load_cnt,
            'observedChannels': observed_channels,
            'missingChannels': missing_channels,
            'completenessRatio': completeness_ratio,
            'isMultiChannelComplete': len(missing_channels) == 0,
            'diagnosticsSummary': summary,
        }

    @staticmethod
    def check_cold_start_bypass(running_samples_count: int) -> Tuple[bool, Optional[str]]:
        """
        Quy Tắc 2: Ngưỡng Khởi Động Nguội & Bỏ Qua Chuỗi Ngắn.
        Nếu số mẫu đo RUNNING sau sửa chữa gần nhất < 15, BỎ QUA mô hình LSTM.
        """
        if running_samples_count < COLD_START_MIN_SAMPLES:
            msg = (
                f"Thiết bị đang trong giai đoạn khởi động nguội / hiệu chuẩn baseline "
                f"({running_samples_count}/{COLD_START_MIN_SAMPLES} lần đo RUNNING). "
                f"Bỏ qua mô hình LSTM, áp dụng bảo trì định kỳ OEM."
            )
            return True, msg
        return False, None

    @staticmethod
    def evaluate_duty_cycle_calendar_days(operating_rul_days: float, duty_cycle_ratio: float = 1.0) -> float:
        """
        Quy Tắc 3: Quy đổi Ngày Vận Hành Thực Tế (OpDays) sang Ngày Dương Lịch (CalendarDays):
        CalendarDays = OperatingDays / Dc (0 < Dc <= 1.0)
        """
        dc = max(0.05, min(1.0, float(duty_cycle_ratio or 1.0)))
        return float(round(operating_rul_days / dc, 1))

    @staticmethod
    def calculate_mc_dropout_uncertainty(predictions: List[float]) -> Dict[str, Any]:
        """
        Quy Tắc 6: Định Lượng Độ Bất Định Bằng Monte Carlo Dropout (M=20).
        Tính Mean, Std Dev, Khoảng tin cậy 90% [Lower, Upper].
        """
        preds = np.array(predictions, dtype=np.float32)
        mu = float(np.mean(preds))
        sigma = float(np.std(preds))
        lower = float(max(0.0, mu - Z_SCORE_90_PERCENT * sigma))
        upper = float(mu + Z_SCORE_90_PERCENT * sigma)
        is_high_uncertainty = bool(sigma > HIGH_UNCERTAINTY_STD_THRESHOLD)

        return {
            'rul_mean': round(mu, 1),
            'rul_std': round(sigma, 2),
            'confidence_lower': round(lower, 1),
            'confidence_upper': round(upper, 1),
            'is_high_uncertainty': is_high_uncertainty
        }

    @staticmethod
    def check_phantom_recovery(
        model_predicted_rul: float,
        previous_rul: Optional[float],
        last_maintenance_action: Optional[str]
    ) -> Tuple[float, bool]:
        """
        Quy Tắc 4: Bẫy Trôi Dạt Khái Niệm Do Bảo Trì Nhỏ & Kẹp Chặn Hồi Phục Ảo.
        Nếu can thiệp gần nhất là MICRO_MAINTENANCE và RUL tăng vọt > 30% so với trước can thiệp:
        - Bật cờ is_phantom_recovery = True
        - Khóa RUL ở mức cũ: min(RUL_model, RUL_prev)
        """
        if previous_rul is None:
            return model_predicted_rul, False

        is_micro = (last_maintenance_action == 'MICRO_MAINTENANCE')
        if is_micro and model_predicted_rul > (previous_rul * PHANTOM_RECOVERY_JUMP_RATIO):
            # Kẹp chặn RUL không cho tăng ảo
            clamped_rul = float(previous_rul)
            return clamped_rul, True

        return model_predicted_rul, False

    @staticmethod
    def apply_monotonic_filter(
        current_rul: float,
        previous_rul: Optional[float],
        is_core_overhaul_completed: bool = False
    ) -> float:
        """
        Quy Tắc 5: Ràng Buộc Suy Thoái Đơn Điệu Vật Lý.
        RUL chỉ được phép tăng khi có CORE_REPLACEMENT.
        Trong điều kiện bình thường: RUL_filtered(t) = min(RUL_prev, RUL_curr + epsilon)
        """
        if previous_rul is None or is_core_overhaul_completed:
            return current_rul

        filtered = min(float(previous_rul), current_rul + MONOTONIC_NOISE_EPSILON)
        return float(round(filtered, 1))

    @staticmethod
    def calculate_dynamic_critical_threshold(lead_time_days: int = 0) -> int:
        """
        Quy Tắc 7: Cảnh Báo Thích Ứng Theo Thời Gian Đặt Hàng Phụ Tùng (Lead-Time Aware).
        Threshold_CRITICAL = max(14, lead_time_days + 5)
        """
        lt = int(lead_time_days or 0)
        return max(MIN_CRITICAL_THRESHOLD_DAYS, lt + LEAD_TIME_SAFETY_BUFFER_DAYS)

    @staticmethod
    def detect_rapid_degradation(
        recent_rul_history: List[float]
    ) -> Tuple[bool, Optional[float]]:
        """
        Quy Tắc 9: Phát Hiện Gia Tốc Suy Thoái Đột Biến (Sudden Catastrophic Spike).
        Theo dõi tốc độ sụt giảm trong 3 lần đo gần nhất:
        - delta RUL >= 5.0 ngày/lần đo
        - Hoặc RUL giảm > 50% trong 3 lần đo liên tiếp
        """
        if len(recent_rul_history) < 3:
            return False, None

        # 3 mốc RUL gần nhất: [t-2, t-1, t]
        r_oldest = recent_rul_history[0]
        r_current = recent_rul_history[-1]

        drop_total = r_oldest - r_current
        drop_rate = drop_total / (len(recent_rul_history) - 1)

        is_rapid = False
        if drop_rate >= RAPID_DEGRADATION_RATE_THRESHOLD:
            is_rapid = True
        elif r_oldest > 0 and (drop_total / r_oldest) >= RAPID_DEGRADATION_PERCENT_THRESHOLD:
            is_rapid = True

        return is_rapid, float(round(drop_rate, 2))

    @classmethod
    def evaluate_risk_level(
        cls,
        rul_op_days: float,
        critical_threshold: int,
        rapid_alert: bool = False
    ) -> str:
        """
        Xác định cấp độ rủi ro:
        - CRITICAL: RUL <= Critical Threshold (động theo lead time) hoặc rapid alert
        - HIGH: RUL <= Critical Threshold + 15 ngày
        - MEDIUM: RUL <= 60 ngày
        - LOW: RUL > 60 ngày
        """
        if rapid_alert or rul_op_days <= critical_threshold:
            return 'CRITICAL'
        elif rul_op_days <= (critical_threshold + 15):
            return 'HIGH'
        elif rul_op_days <= 60.0:
            return 'MEDIUM'
        else:
            return 'LOW'
