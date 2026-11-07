"""
Context-Aware Life-Safety Classifier (Rule 1, Rule 6).
Distinguishes between:
- Active field emergencies (Fire/electrical, gas leak, mechanical entrapment, acid splash)
- Informational / theoretical queries and queries with safe negation (e.g. "Máy không bị cháy nhưng rung mạnh")
Outputs specialized layered safety protocols rather than a generic E-STOP for all cases.
"""

from typing import Dict, Any, Optional
from .constants import (
    EMERGENCY_HAZARDS,
    THEORETICAL_KEYWORDS,
    NEGATION_WORDS,
)


def classify_safety_context(prompt: str) -> Dict[str, Any]:
    """
    Classifies the user query for life-safety emergencies.
    
    Returns:
        dict: {
            'is_emergency': bool,
            'hazard_type': Optional[str],
            'emergency_name': Optional[str],
            'instruction': Optional[str],
            'action_summary': Optional[str],
            'is_theoretical_or_negated': bool,
            'matched_keyword': Optional[str],
        }
    """
    if not prompt or not isinstance(prompt, str):
        return {
            'is_emergency': False,
            'hazard_type': None,
            'emergency_name': None,
            'instruction': None,
            'action_summary': None,
            'is_theoretical_or_negated': False,
            'matched_keyword': None,
        }

    lower_prompt = prompt.lower().strip()

    # 1. Kiểm tra xem câu hỏi có chứa từ phủ định an toàn hay không
    # Ví dụ: "không bị cháy", "chưa xì khói", "không có rò rỉ"
    has_safe_negation = False
    for neg in NEGATION_WORDS:
        if neg in lower_prompt:
            has_safe_negation = True
            break

    # 2. Kiểm tra câu hỏi có mang tính lý thuyết / tìm hiểu nguyên nhân / phòng ngừa không
    # Ví dụ: "nguyên nhân gây chập điện mô tơ", "cách phòng ngừa cháy biến áp"
    is_theoretical = False
    for theo in THEORETICAL_KEYWORDS:
        if theo in lower_prompt:
            is_theoretical = True
            break

    is_theoretical_or_negated = has_safe_negation or is_theoretical

    # Nếu câu mang tính lý thuyết hoặc có phủ định an toàn, không kích hoạt ngắt an toàn khẩn cấp
    if is_theoretical_or_negated:
        return {
            'is_emergency': False,
            'hazard_type': None,
            'emergency_name': None,
            'instruction': None,
            'action_summary': None,
            'is_theoretical_or_negated': True,
            'matched_keyword': None,
        }

    # 3. Quét các danh mục nguy cơ khẩn cấp thời gian thực
    for hazard_type, hazard_info in EMERGENCY_HAZARDS.items():
        for kw in hazard_info['keywords']:
            if kw in lower_prompt:
                return {
                    'is_emergency': True,
                    'hazard_type': hazard_type,
                    'emergency_name': hazard_info['name'],
                    'instruction': hazard_info['instruction'],
                    'action_summary': hazard_info['action_summary'],
                    'is_theoretical_or_negated': False,
                    'matched_keyword': kw,
                }

    return {
        'is_emergency': False,
        'hazard_type': None,
        'emergency_name': None,
        'instruction': None,
        'action_summary': None,
        'is_theoretical_or_negated': False,
        'matched_keyword': None,
    }
