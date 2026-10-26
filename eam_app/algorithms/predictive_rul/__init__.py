"""
Package algorithms.predictive_rul (Phase 11.5).
Deep Learning Predictive Maintenance (LSTM for Remaining Useful Life - RUL).
"""

from .constants import (
    WINDOW_SIZE, FEATURE_DIM, COLD_START_MIN_SAMPLES,
    RUL_MAX_CLIP_DAYS, MC_DROPOUT_PASSES, Z_SCORE_90_PERCENT,
    HIGH_UNCERTAINTY_STD_THRESHOLD, MONOTONIC_NOISE_EPSILON,
    PHANTOM_RECOVERY_JUMP_RATIO, RAPID_DEGRADATION_RATE_THRESHOLD,
    MODEL_VERSION
)
from .model import NumpyLSTMRULPredictor, get_rul_model
from .dataset_pipeline import DegradationFeaturePipeline
from .guardrails import PredictiveRULGuardrails
from .service import RULPredictiveService

__all__ = [
    'WINDOW_SIZE',
    'FEATURE_DIM',
    'COLD_START_MIN_SAMPLES',
    'RUL_MAX_CLIP_DAYS',
    'MC_DROPOUT_PASSES',
    'NumpyLSTMRULPredictor',
    'get_rul_model',
    'DegradationFeaturePipeline',
    'PredictiveRULGuardrails',
    'RULPredictiveService',
]
