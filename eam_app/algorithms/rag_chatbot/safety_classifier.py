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
from .safety_config import ensure_safety_config_loaded


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

    # 1. Tìm các nguy cơ khẩn cấp khớp trong prompt
    matched_hazard = None
    for hazard_type, hazard_info in EMERGENCY_HAZARDS.items():
        for kw in hazard_info['keywords']:
            if kw in lower_prompt:
                matched_hazard = (hazard_type, hazard_info, kw)
                break
        if matched_hazard:
            break

    if not matched_hazard:
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

    hazard_type, hazard_info, kw = matched_hazard

    # 2. Kiểm tra dấu hiệu sự cố thời gian thực / khẩn cấp
    active_emergency_markers = [
        'đang', 'khẩn cấp', 'cấp cứu', 'làm sao dập', 'dập ngay', 'dập lửa', 
        'cứu người', 'bị văng', 'bắn vào', 'bị kẹt', 'đang xì', 'đang cháy',
        'đang bốc khói', 'đang rò rỉ', 'nguy cấp', 'sắp nổ', 'nổ rồi'
    ]
    has_active_marker = any(m in lower_prompt for m in active_emergency_markers)

    # 3. Kiểm tra xem từ khóa nguy cơ này có thực sự bị phủ định an toàn không
    # (Ví dụ: "không bị cháy", "chưa xì gas", "không có rò rỉ khí độc", "chưa từng nổ")
    # NGUYÊN TẮC: Nếu có active emergency marker, sự cố đang diễn ra KHÔNG BAO GIỜ bị phủ định
    # bởi các cụm từ tránh lây lan (như "để không cháy lan", "tránh bùng phát").
    is_negated = False
    if not has_active_marker:
        spread_markers = ['lan', 'rộng', 'sang', 'thêm', 'bùng phát', 'tiếp']
        for neg in NEGATION_WORDS:
            if neg in lower_prompt:
                neg_idx = lower_prompt.find(neg)
                kw_idx = lower_prompt.find(kw)
                
                # Bỏ qua nếu là cụm từ ngăn chặn lan rộng (ví dụ "không cháy lan", "không xì thêm")
                is_spread_context = any(
                    lower_prompt[neg_idx + len(neg):].strip().startswith(sp)
                    for sp in spread_markers
                )
                if is_spread_context:
                    continue

                # Nếu từ phủ định đứng trước từ khóa nguy cơ trong phạm vi gần (<= 25 ký tự)
                if (0 <= kw_idx - neg_idx <= len(neg) + 25) or any(neg_kw in lower_prompt for neg_kw in [
                    f"{neg} {kw}", f"không bị {kw}", f"chưa bị {kw}", f"không hề {kw}", f"chưa hề {kw}"
                ]):
                    is_negated = True
                    break

                # Nếu cụm phủ định bản thân nó đã chứa từ gốc nguy cơ (như 'không cháy', 'không xì', 'chưa nổ')
                # và KHÔNG phải là hỏi về phòng tránh sự cố lan rộng
                if any(stem in neg and stem in kw for stem in ['cháy', 'xì', 'nổ', 'rò', 'chập', 'kẹt', 'bắn']):
                    # Chỉ coi là phủ định nếu nó không đi kèm từ khóa chỉ sự cố lan rộng
                    if not any(sp in lower_prompt for sp in ['cháy lan', 'lửa lan', 'nổ tiếp', 'xì thêm']):
                        is_negated = True
                        break

    # 4. Kiểm tra câu hỏi có mang tính lý thuyết / tìm hiểu nguyên nhân / phòng ngừa định kỳ
    # Ví dụ: "nguyên nhân gây chập điện mô tơ", "cách phòng ngừa cháy biến áp"
    is_theoretical = False
    if not has_active_marker:
        for theo in THEORETICAL_KEYWORDS:
            if theo in lower_prompt:
                is_theoretical = True
                break

    if is_negated or is_theoretical:
        return {
            'is_emergency': False,
            'hazard_type': None,
            'emergency_name': None,
            'instruction': None,
            'action_summary': None,
            'is_theoretical_or_negated': True,
            'matched_keyword': kw,
        }

    # 4. Kích hoạt phản ứng khẩn cấp an toàn sinh mạng
    return {
        'is_emergency': True,
        'hazard_type': hazard_type,
        'emergency_name': hazard_info['name'],
        'instruction': hazard_info['instruction'],
        'action_summary': hazard_info['action_summary'],
        'is_theoretical_or_negated': False,
        'matched_keyword': kw,
    }
