import re
import unicodedata
import math
from typing import Dict, Any, Tuple
from django.utils import timezone
from .constants import (
    BIG_M, PRIORITY_MULTIPLIERS,
    NORM_WEIGHT_DISTANCE, NORM_WEIGHT_SKILL, NORM_WEIGHT_WORKLOAD,
    PENALTY_ZONE_SAME, PENALTY_ZONE_DIFF, PENALTY_ZONE_CONTROLLED, CONTROLLED_ZONES,
    PENALTY_SHIFT_HANDOVER, SHIFT_OVERTIME_LIMIT_HOURS, PENALTY_DISRUPTION,
    MAX_DISTANCE_SCORE, FLOOR_PENALTY_METERS, METERS_TO_SCORE_FACTOR
)

# Common/General plant-wide pool keywords (incur 0 zone transition penalty)
GENERAL_ZONE_TOKENS = {
    'CHUNG', 'ALL', 'ANY', 'DEFAULT', 'TOAN_NHA_MAY', 'TOAN_CONG_TY',
    'CO_DONG', 'COMMON', 'PLANT_WIDE', 'GENERAL', 'NONE', ''
}

# Controlled/Cleanroom zone keywords requiring special gowning/decontamination (+40)
CONTROLLED_ZONE_KEYWORDS = {
    'CLEANROOM', 'PHONG_SACH', 'VO_TRUNG', 'CACH_LY', 'ISOLATION', 'BIO_SAFETY',
    'NGUY_HIEM', 'STERILE', 'PAINT_SHOP'
}


def strip_vietnamese_accents(text: str) -> str:
    """Strips Vietnamese accents/diacritics to ensure resilient cross-matching."""
    if not text:
        return ""
    text = text.replace('đ', 'd').replace('Đ', 'D')
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def normalize_text_token(val: Any) -> str:
    """
    Normalize string token for resilient matching across case, spaces, and diacritics.
    Handles Vietnamese accents, hyphens, and whitespace consistently.
    """
    if val is None:
        return ""
    text = str(val).strip().upper()
    text = strip_vietnamese_accents(text)
    text = re.sub(r'[^A-Z0-9]+', '_', text)
    return text.strip('_')


def calculate_distance_score(tech_x: float, tech_y: float, tech_floor: int,
                             wo_x: float, wo_y: float, wo_floor: int) -> float:
    """
    D_ij: Multi-floor Manhattan Distance normalized to [0, 100].
    D_ij = min(100.0, 0.1 * (|dx| + |dy| + 50 * |dz|))
    If either party has unconfigured/null coordinates, returns 0.0 (non-spatial layout).
    """
    if tech_x is None or tech_y is None or wo_x is None or wo_y is None:
        return 0.0

    # Non-coordinate fallback: If either side has unconfigured (0, 0) coordinates,
    # distance defaults to 0.0 so matching relies entirely on Zone (Pen_zone)
    if (float(tech_x or 0.0) == 0.0 and float(tech_y or 0.0) == 0.0) or \
       (float(wo_x or 0.0) == 0.0 and float(wo_y or 0.0) == 0.0):
        return 0.0

    dx = abs(float(tech_x) - float(wo_x))
    dy = abs(float(tech_y) - float(wo_y))
    dz = abs(int(tech_floor or 1) - int(wo_floor or 1))

    raw_dist = dx + dy + (FLOOR_PENALTY_METERS * dz)
    score = METERS_TO_SCORE_FACTOR * raw_dist
    return round(min(MAX_DISTANCE_SCORE, score), 2)


def calculate_skill_score(tech_level: int, req_level: int) -> float:
    """
    S_ij: Skill gap score.
    Delta = Level_tech - Level_req
    Delta < 0 (under-qualified): 20 * |Delta|
    Delta > 0 (over-qualified): 5 * Delta
    Delta == 0: 0
    """
    t_lvl = int(tech_level or 1)
    r_lvl = int(req_level or 1)
    delta = t_lvl - r_lvl

    if delta < 0:
        return float(20 * abs(delta))
    elif delta > 0:
        return float(5 * delta)
    return 0.0


def calculate_zone_penalty(tech_zone: str, wo_zone: str) -> float:
    """
    Pen_zone: Zone transition penalty.
    - Same zone: 0.0
    - General/plant-wide zones (CHUNG, TOÀN NHÀ MÁY, CƠ ĐỘNG): 0.0
    - Controlled/cleanroom zones: 40.0
    - Different standard zones: 15.0
    Resilient to case, spaces, and Vietnamese diacritics.
    """
    tz = normalize_text_token(tech_zone)
    wz = normalize_text_token(wo_zone)

    # Both empty or exact normalized match
    if not tz or not wz or tz == wz:
        return PENALTY_ZONE_SAME

    # General plant-wide pool (roving tech or plant-wide ticket)
    if tz in GENERAL_ZONE_TOKENS or wz in GENERAL_ZONE_TOKENS:
        return PENALTY_ZONE_SAME

    if any(g in tz for g in {'TOAN_NHA_MAY', 'TOAN_CONG_TY', 'CO_DONG'}) or \
       any(g in wz for g in {'TOAN_NHA_MAY', 'TOAN_CONG_TY', 'CO_DONG'}):
        return PENALTY_ZONE_SAME

    # Controlled/Cleanroom zone check
    if tz in CONTROLLED_ZONES or wz in CONTROLLED_ZONES or \
       any(k in tz for k in CONTROLLED_ZONE_KEYWORDS) or \
       any(k in wz for k in CONTROLLED_ZONE_KEYWORDS):
        return PENALTY_ZONE_CONTROLLED

    return PENALTY_ZONE_DIFF


def calculate_shift_penalty(shift_end_time, duration_hours: float, current_time=None) -> Tuple[float, bool]:
    """
    Pen_shift: Shift handover clash penalty.
    Returns: (penalty_score, is_hard_violation)
    If duration > remaining_shift + 2.0h -> is_hard_violation = True (Big-M)
    If duration > remaining_shift -> penalty = 40.0
    Else -> penalty = 0.0
    """
    if not shift_end_time:
        return 0.0, False

    now = current_time or timezone.now()
    rem_seconds = (shift_end_time - now).total_seconds()
    rem_hours = max(0.0, rem_seconds / 3600.0)

    dur = float(duration_hours or 0.0)

    if dur > rem_hours + SHIFT_OVERTIME_LIMIT_HOURS:
        return BIG_M, True

    if dur > rem_hours:
        return PENALTY_SHIFT_HANDOVER, False

    return 0.0, False


GENERAL_SKILL_TOKENS = {
    'GENERAL', 'NONE', 'ALL', 'ANY', 'CHUNG', 'PHO_THONG', 'TONG_HOP',
    'BAO_TRI_CHUNG', 'BAO_TRI_CO_DIEN_TONG_HOP', 'BAO_DUONG_CHUNG', 'BAO_DUONG',
    'CO_BAN', ''
}

CATEGORY_SYNONYMS = {
    'MECHANICAL': {'CO_KHI', 'MECHANICAL', 'GIA_CONG', 'CHE_TAO', 'BAO_DUONG_MAY'},
    'ELECTRICAL': {'DIEN', 'ELECTRICAL', 'DIEN_CONG_NGHIEP', 'TU_DIEN', 'HA_THE'},
    'HVAC': {'NHIET_LANH', 'HVAC', 'DIEN_LANH', 'THONG_GIO', 'LAM_LANH'},
    'HYDRAULIC': {'THUY_LUC', 'KHI_NEN', 'HYDRAULIC', 'PNEUMATIC'},
    'AUTOMATION': {'TU_DONG_HOA', 'AUTOMATION', 'PLC', 'SCADA', 'ROBOT'},
}


def build_tenant_competency_catalog(tenant) -> Dict[str, Any]:
    """
    Precomputes tenant's master skills and certification equivalence maps
    to make Hungarian matching 100% resilient to custom enterprise naming.
    """
    catalog = {
        'skill_code_to_names': {},     # code_token -> set of (name_token, category_token)
        'skill_name_to_codes': {},     # name_token -> set of code_tokens
        'category_to_codes': {},       # category_token -> set of code_tokens
        'cert_code_to_names': {},      # code_token -> set of name_tokens
        'cert_name_to_codes': {},      # name_token -> set of code_tokens
        'user_valid_certs': {},        # user_id -> {'valid': set(), 'expired': set()}
    }
    if not tenant:
        return catalog

    try:
        from users.models import WorkforceSkill, CertificationType, UserCertification
        # 1. Workforce skills
        skills = WorkforceSkill.objects.filter(tenant=tenant, is_active=True)
        for s in skills:
            c_tok = normalize_text_token(s.code)
            n_tok = normalize_text_token(s.name)
            cat_tok = normalize_text_token(s.category)

            catalog['skill_code_to_names'].setdefault(c_tok, set()).update([n_tok, cat_tok])
            catalog['skill_name_to_codes'].setdefault(n_tok, set()).add(c_tok)
            if cat_tok:
                catalog['category_to_codes'].setdefault(cat_tok, set()).add(c_tok)

        # 2. Certification types
        certs = CertificationType.objects.filter(tenant=tenant, is_active=True)
        for c in certs:
            c_tok = normalize_text_token(c.code)
            n_tok = normalize_text_token(c.name)
            catalog['cert_code_to_names'].setdefault(c_tok, set()).add(n_tok)
            catalog['cert_name_to_codes'].setdefault(n_tok, set()).add(c_tok)

        # 3. User certifications
        user_certs = UserCertification.objects.filter(tenant=tenant).select_related('certification_type')
        for uc in user_certs:
            uid = str(uc.user_id)
            c_tok = normalize_text_token(uc.certification_type.code)
            n_tok = normalize_text_token(uc.certification_type.name)
            if uid not in catalog['user_valid_certs']:
                catalog['user_valid_certs'][uid] = {'valid': set(), 'expired': set()}

            if uc.is_valid:
                catalog['user_valid_certs'][uid]['valid'].update([c_tok, n_tok])
            else:
                catalog['user_valid_certs'][uid]['expired'].update([c_tok, n_tok])
    except Exception:
        pass

    return catalog


def is_skill_satisfied(required_skill: str, tech_skills_list: list, catalog: Dict[str, Any] = None) -> bool:
    """
    Evaluates whether a technician's skills satisfy the required work order skill.
    Supports:
    - Default 'GENERAL' / common maintenance (all techs qualify)
    - Code <-> Name bidirectional matching from tenant Master Data
    - Category & domain synonym matching (e.g. AUTOMATION <-> TỰ ĐỘNG HÓA)
    - Case-insensitive and trimmed token comparison
    """
    if not required_skill:
        return True

    req_tok = normalize_text_token(required_skill)
    if req_tok in GENERAL_SKILL_TOKENS:
        return True

    tech_tokens = set()
    for s in (tech_skills_list or []):
        st = normalize_text_token(s)
        if not st:
            continue
        tech_tokens.add(st)
        if catalog:
            names_and_cats = catalog.get('skill_code_to_names', {}).get(st)
            if names_and_cats:
                tech_tokens.update(names_and_cats)
            codes = catalog.get('skill_name_to_codes', {}).get(st)
            if codes:
                tech_tokens.update(codes)

    # 1. Direct or expanded match
    if req_tok in tech_tokens:
        return True

    # 2. Check if req_tok is a name mapped to a code the technician has
    if catalog:
        mapped_codes = catalog.get('skill_name_to_codes', {}).get(req_tok)
        if mapped_codes and any(c in tech_tokens for c in mapped_codes):
            return True

        cat_codes = catalog.get('category_to_codes', {}).get(req_tok)
        if cat_codes and any(c in tech_tokens for c in cat_codes):
            return True

    # 3. Check domain category synonyms
    for cat_key, synonyms in CATEGORY_SYNONYMS.items():
        if req_tok == cat_key or req_tok in synonyms:
            if any(t in synonyms or t == cat_key for t in tech_tokens):
                return True

    return False


def is_certification_satisfied(required_cert: str, tech_certs_list: list, tech_user=None, catalog: Dict[str, Any] = None) -> bool:
    """
    Evaluates whether a technician has the required safety certification.
    Supports:
    - Code <-> Name equivalence
    - Structured UserCertification check with expiration tracking
    - Case-insensitive comparison
    """
    if not required_cert:
        return True

    req_tok = normalize_text_token(required_cert)
    if not req_tok or req_tok in {'NONE', 'CHUNG', 'KHONG'}:
        return True

    valid_tokens = set(normalize_text_token(c) for c in (tech_certs_list or []))

    if catalog and tech_user:
        uid = str(getattr(tech_user, 'id', tech_user))
        user_cert_data = catalog.get('user_valid_certs', {}).get(uid)
        if user_cert_data:
            valid_tokens.update(user_cert_data.get('valid', set()))
            valid_tokens.difference_update(user_cert_data.get('expired', set()))
    elif tech_user:
        try:
            from users.models import UserCertification
            ucs = UserCertification.objects.filter(user=tech_user).select_related('certification_type')
            for uc in ucs:
                c_tok = normalize_text_token(uc.certification_type.code)
                n_tok = normalize_text_token(uc.certification_type.name)
                if uc.is_valid:
                    valid_tokens.update([c_tok, n_tok])
                else:
                    valid_tokens.difference_update([c_tok, n_tok])
        except Exception:
            pass

    if catalog:
        expanded = set(valid_tokens)
        for vt in valid_tokens:
            names = catalog.get('cert_code_to_names', {}).get(vt)
            if names:
                expanded.update(names)
            codes = catalog.get('cert_name_to_codes', {}).get(vt)
            if codes:
                expanded.update(codes)
        valid_tokens = expanded

    if req_tok in valid_tokens:
        return True

    if catalog:
        mapped_codes = catalog.get('cert_name_to_codes', {}).get(req_tok)
        if mapped_codes and any(c in valid_tokens for c in mapped_codes):
            return True

    return False


def evaluate_pair_cost(tech_profile, wo_slot, active_workload: int = 0,
                       has_in_progress: bool = False, current_time=None,
                       catalog: Dict[str, Any] = None) -> Tuple[float, Dict[str, Any], str]:
    """
    Evaluates total composite cost C_ij between a technician profile and a work order slot.
    Returns: (final_cost, breakdown_dict, explanation_text)
    """
    now = current_time or timezone.now()
    tech = tech_profile
    wo = wo_slot

    if catalog is None and getattr(tech, 'tenant', None):
        catalog = build_tenant_competency_catalog(tech.tenant)

    # 1. HARD CONSTRAINT CHECKS (Big-M Guardrails)
    reasons_hard = []

    # 1.1 Required Skill check (Rule 8 - Flexible & Tenant-Aware)
    if wo.required_skill and not is_skill_satisfied(wo.required_skill, tech.skills, catalog=catalog):
        reasons_hard.append(f"Thiếu chuyên môn '{wo.required_skill}'")

    # 1.2 Safety Certification check (Rule 8 - Flexible & Tenant-Aware)
    if wo.required_certification and not is_certification_satisfied(
        wo.required_certification, tech.certifications, tech_user=getattr(tech, 'user', None), catalog=catalog
    ):
        reasons_hard.append(f"Thiếu chứng chỉ an toàn '{wo.required_certification}'")

    # 1.3 Shift Overtime Hard Limit check (Rule 3)
    shift_pen, is_shift_hard = calculate_shift_penalty(
        tech.shift_end_time,
        wo.estimated_duration_hours,
        current_time=now
    )
    if is_shift_hard:
        reasons_hard.append(f"Thời gian việc {wo.estimated_duration_hours}h vượt quá ca trực hơn 2h tăng ca")

    if reasons_hard:
        breakdown = {
            "distanceScore": 0.0,
            "skillScore": 0.0,
            "workloadScore": 0.0,
            "priorityMultiplier": PRIORITY_MULTIPLIERS.get(wo.priority, 1.0),
            "zonePenalty": 0.0,
            "shiftPenalty": BIG_M,
            "disruptionPenalty": 0.0,
            "isHardViolation": True,
            "violationReason": "; ".join(reasons_hard)
        }
        explanation = f"VI PHẠM RÀNG BUỘC CỨNG Big-M: {'; '.join(reasons_hard)}."
        return BIG_M, breakdown, explanation

    # 2. SOFT COMPONENT SCORES
    dist_score = calculate_distance_score(
        tech.coords_x, tech.coords_y, tech.floor_level,
        wo.coords_x, wo.coords_y, wo.floor_level
    )
    skill_score = calculate_skill_score(tech.skill_level, wo.min_skill_level)
    workload_score = float(25.0 * max(0, active_workload))
    zone_pen = calculate_zone_penalty(tech.zone_id, wo.zone_id)
    disrupt_pen = PENALTY_DISRUPTION if has_in_progress else 0.0

    multiplier = PRIORITY_MULTIPLIERS.get(wo.priority, 1.0)

    # Core Formula (Spec 4.1):
    # C_base = Priority_Multiplier * (w_d * D_ij + w_s * S_ij) + w_w * W_i + Pen_zone + Pen_shift + Pen_disrupt
    weighted_dist_skill = (NORM_WEIGHT_DISTANCE * dist_score) + (NORM_WEIGHT_SKILL * skill_score)
    amplified_dist_skill = multiplier * weighted_dist_skill
    weighted_workload = NORM_WEIGHT_WORKLOAD * workload_score

    total_cost = round(
        amplified_dist_skill + weighted_workload + zone_pen + shift_pen + disrupt_pen,
        2
    )

    breakdown = {
        "distanceScore": dist_score,
        "skillScore": skill_score,
        "workloadScore": workload_score,
        "priorityMultiplier": multiplier,
        "zonePenalty": zone_pen,
        "shiftPenalty": shift_pen,
        "disruptionPenalty": disrupt_pen,
        "isHardViolation": False,
        "violationReason": ""
    }

    # Generate Explainable Narrative for UI Tooltip
    narrative_parts = []
    if multiplier > 1.0:
        narrative_parts.append(f"Việc {wo.priority} (hệ số x{multiplier})")
    narrative_parts.append(f"Khoảng cách {dist_score}đ")

    delta_lvl = (tech.skill_level or 1) - (wo.min_skill_level or 1)
    if delta_lvl == 0:
        narrative_parts.append(f"đúng bậc thợ - Bậc {tech.skill_level}")
    elif delta_lvl > 0:
        narrative_parts.append(f"thừa {delta_lvl} bậc thợ")
    else:
        narrative_parts.append(f"thiếu {abs(delta_lvl)} bậc thợ")

    if zone_pen == 0.0:
        narrative_parts.append("cùng khu vực")
    elif zone_pen >= PENALTY_ZONE_CONTROLLED:
        narrative_parts.append("phạt qua phòng sạch: +40đ")
    else:
        narrative_parts.append("khác phân xưởng: +15đ")

    if shift_pen > 0:
        narrative_parts.append("phạt gần hết ca: +40đ")
    else:
        narrative_parts.append("đủ thời gian ca trực")

    if disrupt_pen > 0:
        narrative_parts.append("đang có việc dở dang: +15đ")

    explanation = ". ".join(narrative_parts) + "."

    return total_cost, breakdown, explanation
