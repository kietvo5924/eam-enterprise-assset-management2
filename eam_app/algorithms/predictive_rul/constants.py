"""
Constants and Hyperparameters for Deep Learning LSTM RUL Predictive Maintenance (Phase 11.5).
"""

# Window and Feature Shape
WINDOW_SIZE = 30           # Ma trận trượt W = 30 bước đo liên tiếp
FEATURE_DIM = 4            # [Vibration RMS, Delta T (bearing - ambient), Pressure, Load Factor]

# Feature indices
IDX_VIBRATION = 0
IDX_DELTA_TEMP = 1
IDX_PRESSURE = 2
IDX_LOAD_FACTOR = 3

# Minimum sample count for cold start bypass (Rule 2)
COLD_START_MIN_SAMPLES = 15

# Target clipping threshold for piece-wise linear RUL (Rule 11)
RUL_MAX_CLIP_DAYS = 125.0

# Monte Carlo Dropout Parameters (Rule 6)
MC_DROPOUT_PASSES = 20
MC_DROPOUT_RATE = 0.20
Z_SCORE_90_PERCENT = 1.645
HIGH_UNCERTAINTY_STD_THRESHOLD = 10.0  # Nếu sigma > 10.0 ngày -> High Uncertainty

# Monotonic degradation filter noise tolerance (Rule 5)
MONOTONIC_NOISE_EPSILON = 1.0  # Dung sai nhiễu cảm biến cho phép: 1.0 ngày

# Phantom recovery threshold ratio (Rule 4)
# Nếu sau khi MICRO_MAINTENANCE mà RUL tăng vọt > 30% so với RUL trước can thiệp -> Bẫy hồi phục ảo
PHANTOM_RECOVERY_JUMP_RATIO = 1.30

# Rapid degradation detection threshold (Rule 9)
# RUL sụt giảm >= 5.0 ngày/lần đo hoặc giảm > 50% trong 3 lần đo liên tiếp
RAPID_DEGRADATION_RATE_THRESHOLD = 5.0
RAPID_DEGRADATION_PERCENT_THRESHOLD = 0.50

# Dynamic Lead Time buffer (Rule 7)
LEAD_TIME_SAFETY_BUFFER_DAYS = 5
MIN_CRITICAL_THRESHOLD_DAYS = 14

# Model Architecture Dimensions
LSTM_HIDDEN_DIM_1 = 64
LSTM_HIDDEN_DIM_2 = 32
MODEL_VERSION = 'v1.0.0-cpu'

# Default Normalization Ranges for Scaling (Min-Max Scaling to [0, 1])
# Dựa trên giới hạn vật lý và tập dữ liệu FEMTO PHM 2012 / UCI AI4I
FEATURE_BOUNDS = {
    'vibration_rms': {'min': 0.0, 'max': 15.0},      # mm/s RMS (ISO 10816 Zone A -> Zone D)
    'delta_temp': {'min': 0.0, 'max': 60.0},         # °C (Chênh lệch nhiệt độ vỏ ổ trục - môi trường)
    'pressure': {'min': 0.0, 'max': 25.0},           # bar (Áp suất thủy lực/áp suất bơm)
    'load_factor': {'min': 0.2, 'max': 1.6},         # Hệ số tải động cơ (0.2 -> 1.6 định mức)
}
