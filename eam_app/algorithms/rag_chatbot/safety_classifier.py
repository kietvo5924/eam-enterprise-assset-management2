"""
Context-Aware Life-Safety Classifier (Rule 1, Rule 6).
Distinguishes between:
- Active field emergencies (Fire/electrical, gas leak, mechanical entrapment, acid splash)
- Informational / theoretical queries and queries with safe negation (e.g. "Máy không bị cháy nhưng rung mạnh")
Outputs specialized layered safety protocols rather than a generic E-STOP for all cases.
"""

import re
from typing import Dict, Any, Optional
from .constants import (
    EMERGENCY_HAZARDS,
    THEORETICAL_KEYWORDS,
    NEGATION_WORDS,
)
from .safety_config import ensure_safety_config_loaded

# Direct hazard negation regex pattern: matches negation words with optional auxiliary verbs and hazard status nouns
NEGATION_PATTERN = re.compile(
    r'^(?:(?:máy|thiết bị|hệ thống|tủ|bình|khu vực|hiện tại|thực tế)\s+)?'
    r'(?:hoàn toàn\s+)?'
    r'(?:không|chưa|chẳng|tránh)'
    r'(?:\s+hề)?'
    r'(?:\s+(?:bị|có|thấy|phát hiện|xảy ra|xuất hiện|gặp|gây|phải))?'
    r'(?:\s+(?:nguy cơ|hiện tượng|sự cố|dấu hiệu|tình trạng|vấn đề))?$',
    re.IGNORECASE
)
CLAUSE_DELIMITERS = [',', ';', '.', '!', '?', '\n', ' nhưng ', ' tuy nhiên ', ' song ', ' mà ', ' trong khi ']
EMERGENCY_ACTION_MARKERS = [
    'khẩn cấp', 'cấp cứu', 'làm sao dập', 'dập ngay', 'dập lửa',
    'cứu người', 'bị văng', 'bắn vào', 'bị kẹt', 'đang xì', 'đang cháy',
    'đang bốc khói', 'đang rò rỉ', 'nguy cấp', 'sắp nổ', 'nổ rồi', 'cháy rồi',
    'cháy khẩn cấp', 'dừng máy khẩn cấp'
]
SPREAD_MARKERS = ['lan', 'rộng', 'sang', 'thêm', 'bùng phát', 'tiếp']
EXTENDED_THEORETICAL = list(THEORETICAL_KEYWORDS) + [
    'quy trình xử lý', 'hướng dẫn xử lý', 'phương án xử lý', 'tiêu chuẩn', 'sổ tay',
    'làm thế nào để tránh'
]


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

    ensure_safety_config_loaded()
    lower_prompt = prompt.lower().strip()

    # 1. Tìm tất cả các nguy cơ khẩn cấp khớp trong prompt
    matches = []
    for hazard_type, hazard_info in EMERGENCY_HAZARDS.items():
        if not isinstance(hazard_info, dict):
            continue
        keywords = hazard_info.get('keywords', [])
        if not isinstance(keywords, list):
            continue
        for kw in keywords:
            if not isinstance(kw, str) or not kw.strip():
                continue
            kw_lower = kw.lower().strip()
            start = 0
            while True:
                idx = lower_prompt.find(kw_lower, start)
                if idx == -1:
                    break
                matches.append({
                    'hazard_type': hazard_type,
                    'hazard_info': hazard_info,
                    'kw': kw,
                    'start': idx,
                    'end': idx + len(kw_lower),
                })
                start = idx + len(kw_lower)

    if not matches:
        # Không có từ khóa nguy cơ nào, nhưng kiểm tra xem có phủ định an toàn hoặc lý thuyết không
        has_safe_indicator = (
            any(neg in lower_prompt for neg in NEGATION_WORDS) or 
            any(theo in lower_prompt for theo in THEORETICAL_KEYWORDS)
        )
        return {
            'is_emergency': False,
            'hazard_type': None,
            'emergency_name': None,
            'instruction': None,
            'action_summary': None,
            'is_theoretical_or_negated': has_safe_indicator,
            'matched_keyword': None,
        }

    # Sắp xếp các nguy cơ khớp theo vị trí xuất hiện trong câu
    matches.sort(key=lambda m: (m['start'], -(m['end'] - m['start'])))

    active_hazards = []
    for m in matches:
        start, end = m['start'], m['end']

        # Xác định phạm vi mệnh đề chứa nguy cơ cụ thể (clause-aware boundary)
        left_text = lower_prompt[:start]
        clause_start = 0
        for delim in CLAUSE_DELIMITERS:
            pos = left_text.rfind(delim)
            if pos != -1:
                delim_end = pos + len(delim)
                if delim_end > clause_start:
                    clause_start = delim_end

        clause_prefix = lower_prompt[clause_start:start].strip()
        suffix = lower_prompt[end:min(len(lower_prompt), end + 30)].strip()

        # Bỏ qua nếu từ khóa này thuộc ngữ cảnh phòng tránh lan rộng (ví dụ "không cháy lan", "tránh xì thêm")
        is_spread_context = any(suffix.startswith(sp) for sp in SPREAD_MARKERS)

        tokens = clause_prefix.split()
        is_actively_underway = bool(tokens and tokens[-1] in ('đang', 'vừa', 'mới'))

        # Kiểm tra phủ định trực tiếp vào nguy cơ này trong phạm vi mệnh đề
        is_negated = False
        if not is_spread_context and clause_prefix:
            if NEGATION_PATTERN.match(clause_prefix):
                is_negated = True
            else:
                if tokens and tokens[-1] in ('không', 'chưa', 'chẳng', 'tránh'):
                    is_negated = True
                elif len(tokens) >= 2 and f"{tokens[-2]} {tokens[-1]}" in ('không bị', 'chưa bị', 'không có', 'chưa có', 'không hề', 'tránh bị', 'chẳng bị'):
                    if len(tokens) == 2 or tokens[-3] in ('máy', 'thiết bị', 'tủ', 'bình', 'hoàn toàn', 'để', 'nhằm'):
                        is_negated = True

        # Kiểm tra câu hỏi lý thuyết / tìm hiểu nguyên nhân / phòng ngừa định kỳ
        is_theoretical = False
        if not is_actively_underway:
            has_prompt_theo = any(theo in lower_prompt for theo in EXTENDED_THEORETICAL)
            if has_prompt_theo:
                # Chỉ coi là khẩn cấp nếu có lời kêu cứu/hành động khẩn cấp thực sự
                has_active_call = any(act in lower_prompt for act in EMERGENCY_ACTION_MARKERS)
                if not has_active_call:
                    is_theoretical = True

        if not is_negated and not is_theoretical:
            active_hazards.append(m)

    if active_hazards:
        h = active_hazards[0]
        hazard_info = h['hazard_info']
        return {
            'is_emergency': True,
            'hazard_type': h['hazard_type'],
            'emergency_name': hazard_info.get('name', ''),
            'instruction': hazard_info.get('instruction', ''),
            'action_summary': hazard_info.get('action_summary', ''),
            'is_theoretical_or_negated': False,
            'matched_keyword': h['kw'],
        }

    # Tất cả các nguy cơ khớp đều bị phủ định trực tiếp hoặc mang tính lý thuyết
    return {
        'is_emergency': False,
        'hazard_type': None,
        'emergency_name': None,
        'instruction': None,
        'action_summary': None,
        'is_theoretical_or_negated': True,
        'matched_keyword': matches[0]['kw'],
    }
