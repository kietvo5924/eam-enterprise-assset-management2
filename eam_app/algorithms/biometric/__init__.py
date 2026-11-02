"""
Biometric & Spatial Micro-Geofencing Package (Phase 11.7)
MobileFaceNet 128-d Metric Learning & ESP32 Universal BLE Beacon Proximity.
"""

from .proximity_engine import calculate_ble_log_distance, verify_ble_proximity
from .cosine_similarity import (
    calculate_cosine_similarity_from_scratch,
    verify_face_cosine_similarity,
    normalize_l2_from_scratch,
)
from .gatekeeper import verify_start_work_order_gate, verify_complete_work_order_gate

__all__ = [
    'calculate_ble_log_distance',
    'verify_ble_proximity',
    'calculate_cosine_similarity_from_scratch',
    'verify_face_cosine_similarity',
    'normalize_l2_from_scratch',
    'verify_start_work_order_gate',
    'verify_complete_work_order_gate',
]
