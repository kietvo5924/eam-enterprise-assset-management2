"""
Unit and Integration Test Suite: Custom Enterprise Naming in Hungarian Algorithm
Verifies that custom skills, certifications, and categories named according to
enterprise-specific conventions are flexibly and accurately recognized by the
Hungarian optimization algorithm.
"""
import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from algorithms.hungarian.cost_matrix import (
    normalize_text_token,
    is_skill_satisfied,
    is_certification_satisfied,
    evaluate_pair_cost,
    calculate_distance_score,
    calculate_zone_penalty,
    GENERAL_SKILL_TOKENS,
    CATEGORY_SYNONYMS,
    BIG_M
)


class TestCustomEnterpriseNamingInHungarian(unittest.TestCase):
    def setUp(self):
        # Build a representative tenant competency catalog with enterprise-custom naming
        self.tenant_catalog = {
            'skill_code_to_names': {
                'ROBOT_ABB_6700': {'KY_THUAT_VIEN_ROBOT_ABB_IRB6700', 'AUTOMATION'},
                'HAN_AP_LUC_6G': {'THO_HAN_AP_LUC_ONG_6G', 'MECHANICAL'},
                'DET_TRON_MAYER': {'KY_THUAT_MAY_DET_TRON_MAYER', 'DET_MAY'},  # Enterprise-custom category
            },
            'skill_name_to_codes': {
                'KY_THUAT_VIEN_ROBOT_ABB_IRB6700': {'ROBOT_ABB_6700'},
                'THO_HAN_AP_LUC_ONG_6G': {'HAN_AP_LUC_6G'},
                'KY_THUAT_MAY_DET_TRON_MAYER': {'DET_TRON_MAYER'},
            },
            'category_to_codes': {
                'AUTOMATION': {'ROBOT_ABB_6700'},
                'MECHANICAL': {'HAN_AP_LUC_6G'},
                'DET_MAY': {'DET_TRON_MAYER'},
            },
            'cert_code_to_names': {
                'CERT_PCCC_CO_SO': {'CHUNG_CHI_PHONG_CHAY_CHUA_CHAY_CO_SO_CAP_2'},
                'CERT_AN_TOAN_HOA_CHAT': {'CHUNG_CHI_AN_TOAN_HOA_CHAT_VA_DUNG_MOI'},
            },
            'cert_name_to_codes': {
                'CHUNG_CHI_PHONG_CHAY_CHUA_CHAY_CO_SO_CAP_2': {'CERT_PCCC_CO_SO'},
                'CHUNG_CHI_AN_TOAN_HOA_CHAT_VA_DUNG_MOI': {'CERT_AN_TOAN_HOA_CHAT'},
            },
            'user_valid_certs': {
                'user-tech-1': {
                    'valid': {'CERT_PCCC_CO_SO', 'CHUNG_CHI_PHONG_CHAY_CHUA_CHAY_CO_SO_CAP_2'},
                    'expired': set()
                },
                'user-tech-2': {
                    'valid': set(),
                    'expired': {'CERT_AN_TOAN_HOA_CHAT', 'CHUNG_CHI_AN_TOAN_HOA_CHAT_VA_DUNG_MOI'}
                }
            }
        }

    # ---------------------------------------------------------
    # 1. TEXT TOKEN NORMALIZATION
    # ---------------------------------------------------------
    def test_01_token_normalization(self):
        """Token normalization handles whitespace, casing, hyphens, and accents."""
        self.assertEqual(normalize_text_token("  Robot - ABB "), "ROBOT_ABB")
        self.assertEqual(normalize_text_token("Kỹ thuật viên Robot"), "KY_THUAT_VIEN_ROBOT")
        self.assertEqual(normalize_text_token(None), "")
        self.assertEqual(normalize_text_token(""), "")

    # ---------------------------------------------------------
    # 2. EXACT CODE MATCHING
    # ---------------------------------------------------------
    def test_02_exact_custom_code_matching(self):
        """Technician holding custom code ROBOT_ABB_6700 matches required skill ROBOT_ABB_6700."""
        tech_skills = ['ROBOT_ABB_6700']
        self.assertTrue(is_skill_satisfied('ROBOT_ABB_6700', tech_skills, self.tenant_catalog))
        self.assertTrue(is_skill_satisfied('robot_abb_6700', tech_skills, self.tenant_catalog))
        self.assertTrue(is_skill_satisfied('  ROBOT-ABB-6700  ', tech_skills, self.tenant_catalog))

    # ---------------------------------------------------------
    # 3. CODE VS HUMAN NAME BIDIRECTIONAL MATCHING
    # ---------------------------------------------------------
    def test_03_wo_uses_custom_name_tech_holds_code(self):
        """WO specifies human-readable enterprise name, technician holds code."""
        tech_skills = ['ROBOT_ABB_6700']
        required_name = "Kỹ thuật viên Robot ABB IRB6700"
        self.assertTrue(is_skill_satisfied(required_name, tech_skills, self.tenant_catalog))

    def test_04_wo_uses_code_tech_holds_custom_name(self):
        """WO specifies enterprise code, technician profile stores human-readable name."""
        tech_skills = ['Kỹ thuật viên Robot ABB IRB6700']
        required_code = "ROBOT_ABB_6700"
        self.assertTrue(is_skill_satisfied(required_code, tech_skills, self.tenant_catalog))

    # ---------------------------------------------------------
    # 4. CATEGORY & DOMAIN SYNONYM MATCHING
    # ---------------------------------------------------------
    def test_05_category_matching_standard_domain(self):
        """WO requires broad AUTOMATION / Tự động hóa, technician with custom robot skill qualifies."""
        tech_skills = ['ROBOT_ABB_6700']
        # Required as English domain
        self.assertTrue(is_skill_satisfied('AUTOMATION', tech_skills, self.tenant_catalog))
        # Required as Vietnamese domain synonym
        self.assertTrue(is_skill_satisfied('Tự động hóa', tech_skills, self.tenant_catalog))

    def test_06_custom_enterprise_category_matching(self):
        """WO requires enterprise-defined category 'Dệt may', tech with 'DET_TRON_MAYER' qualifies."""
        tech_skills = ['DET_TRON_MAYER']
        self.assertTrue(is_skill_satisfied('DET_MAY', tech_skills, self.tenant_catalog))
        self.assertTrue(is_skill_satisfied('Dệt may', tech_skills, self.tenant_catalog))

    # ---------------------------------------------------------
    # 5. GENERAL MAINTENANCE RESILIENCE
    # ---------------------------------------------------------
    def test_07_general_work_order_acceptance(self):
        """Specialized technicians are not locked out of general maintenance work orders."""
        tech_skills = ['ROBOT_ABB_6700']  # Doesn't have literal 'GENERAL'
        self.assertTrue(is_skill_satisfied('GENERAL', tech_skills, self.tenant_catalog))
        self.assertTrue(is_skill_satisfied('Chung', tech_skills, self.tenant_catalog))
        self.assertTrue(is_skill_satisfied('Bảo dưỡng chung', tech_skills, self.tenant_catalog))
        self.assertTrue(is_skill_satisfied('', tech_skills, self.tenant_catalog))
        self.assertTrue(is_skill_satisfied(None, tech_skills, self.tenant_catalog))

    # ---------------------------------------------------------
    # 6. HARD CONSTRAINT SAFETY: SKILL MISMATCH REJECTION
    # ---------------------------------------------------------
    def test_08_skill_mismatch_strictly_rejected(self):
        """Technician holding ROBOT skill CANNOT satisfy specialized 6G welding skill."""
        tech_skills = ['ROBOT_ABB_6700']
        self.assertFalse(is_skill_satisfied('HAN_AP_LUC_6G', tech_skills, self.tenant_catalog))
        self.assertFalse(is_skill_satisfied('Thợ hàn áp lực ống 6G', tech_skills, self.tenant_catalog))

    # ---------------------------------------------------------
    # 7. CUSTOM CERTIFICATION RESOLUTION
    # ---------------------------------------------------------
    def test_09_custom_certification_code_and_name_equivalence(self):
        """Certification matches both by custom code and enterprise name."""
        tech_certs = ['CERT_PCCC_CO_SO']
        tech_user = MagicMock()
        tech_user.id = 'user-tech-1'

        # Match by exact code
        self.assertTrue(is_certification_satisfied('CERT_PCCC_CO_SO', tech_certs, tech_user, self.tenant_catalog))
        # Match by enterprise custom name
        self.assertTrue(is_certification_satisfied(
            'Chứng chỉ Phòng cháy Chữa cháy Cơ sở Cấp 2', tech_certs, tech_user, self.tenant_catalog
        ))

    # ---------------------------------------------------------
    # 8. EXPIRED CERTIFICATION STRICT EXCLUSION (SAFETY GUARDRAIL)
    # ---------------------------------------------------------
    def test_10_expired_certification_fails_even_if_in_cached_list(self):
        """If UserCertification is expired, technician is REJECTED even if cached in list."""
        # Tech has cert code in legacy list, but user_valid_certs marks it expired
        tech_certs = ['CERT_AN_TOAN_HOA_CHAT']
        tech_user = MagicMock()
        tech_user.id = 'user-tech-2'

        self.assertFalse(is_certification_satisfied('CERT_AN_TOAN_HOA_CHAT', tech_certs, tech_user, self.tenant_catalog))
        self.assertFalse(is_certification_satisfied(
            'Chứng chỉ An toàn Hóa chất & Dung môi', tech_certs, tech_user, self.tenant_catalog
        ))

    # ---------------------------------------------------------
    # 9. EVALUATE PAIR COST INTEGRATION & BIG-M VERIFICATION
    # ---------------------------------------------------------
    def test_11_evaluate_pair_cost_qualified_technician(self):
        """Qualified technician with custom skill receives normal finite cost."""
        tech = MagicMock()
        tech.user_id = 'user-tech-1'
        tech.user = MagicMock(id='user-tech-1')
        tech.skills = ['ROBOT_ABB_6700']
        tech.certifications = ['CERT_PCCC_CO_SO']
        tech.skill_level = 3
        tech.coords_x = 10.0
        tech.coords_y = 10.0
        tech.floor_level = 1
        tech.zone_id = 'ZONE_A'
        tech.shift_end_time = None
        tech.tenant = None

        wo = MagicMock()
        wo.required_skill = 'Kỹ thuật viên Robot ABB IRB6700'  # Enterprise custom name
        wo.min_skill_level = 2
        wo.required_certification = 'CERT_PCCC_CO_SO'
        wo.estimated_duration_hours = 2.0
        wo.coords_x = 12.0
        wo.coords_y = 10.0
        wo.floor_level = 1
        wo.zone_id = 'ZONE_A'
        wo.priority = 'HIGH'

        cost, breakdown, explanation = evaluate_pair_cost(
            tech_profile=tech,
            wo_slot=wo,
            active_workload=0,
            has_in_progress=False,
            catalog=self.tenant_catalog
        )

        self.assertLess(cost, 1000.0, f"Expected normal cost, got {cost}")
        self.assertFalse(breakdown['isHardViolation'])
        self.assertNotIn("VI PHẠM RÀNG BUỘC CỨNG", explanation)

    def test_12_evaluate_pair_cost_unqualified_technician_big_m(self):
        """Unqualified technician receives BIG_M penalty (>= 10,000,000)."""
        tech = MagicMock()
        tech.user_id = 'user-tech-1'
        tech.user = MagicMock(id='user-tech-1')
        tech.skills = ['ROBOT_ABB_6700']  # Doesn't have welding
        tech.certifications = ['CERT_PCCC_CO_SO']
        tech.skill_level = 3
        tech.coords_x = 10.0
        tech.coords_y = 10.0
        tech.floor_level = 1
        tech.zone_id = 'ZONE_A'
        tech.shift_end_time = None
        tech.tenant = None

        wo = MagicMock()
        wo.required_skill = 'HAN_AP_LUC_6G'  # Requires welding
        wo.min_skill_level = 2
        wo.required_certification = None
        wo.estimated_duration_hours = 2.0
        wo.coords_x = 12.0
        wo.coords_y = 10.0
        wo.floor_level = 1
        wo.zone_id = 'ZONE_A'
        wo.priority = 'HIGH'

        cost, breakdown, explanation = evaluate_pair_cost(
            tech_profile=tech,
            wo_slot=wo,
            active_workload=0,
            has_in_progress=False,
            catalog=self.tenant_catalog
        )

        self.assertGreaterEqual(cost, BIG_M)
        self.assertTrue(breakdown['isHardViolation'])
        self.assertIn("Thiếu chuyên môn 'HAN_AP_LUC_6G'", breakdown['violationReason'])

    # ---------------------------------------------------------
    # 10. MULTI-TENANT ISOLATION
    # ---------------------------------------------------------
    def test_13_multi_tenant_catalog_isolation(self):
        """Tenant 1's custom skills cannot be recognized in Tenant 2's catalog."""
        catalog_tenant_2 = {
            'skill_code_to_names': {
                'SKILL_T2_SOLAR': {'KY_SU_PIN_MAT_TROI', 'RENEWABLE'},
            },
            'skill_name_to_codes': {
                'KY_SU_PIN_MAT_TROI': {'SKILL_T2_SOLAR'},
            },
            'category_to_codes': {
                'RENEWABLE': {'SKILL_T2_SOLAR'},
            },
            'cert_code_to_names': {},
            'cert_name_to_codes': {},
            'user_valid_certs': {}
        }
        # Tech holds Tenant 1 custom skill ROBOT_ABB_6700
        tech_skills = ['ROBOT_ABB_6700']

        # In Tenant 1 catalog: matches
        self.assertTrue(is_skill_satisfied('Kỹ thuật viên Robot ABB IRB6700', tech_skills, self.tenant_catalog))

        # In Tenant 2 catalog: must NOT match (cross-tenant isolation)
        self.assertFalse(is_skill_satisfied('Kỹ thuật viên Robot ABB IRB6700', tech_skills, catalog_tenant_2))
        self.assertFalse(is_skill_satisfied('SKILL_T2_SOLAR', tech_skills, catalog_tenant_2))

    # ---------------------------------------------------------
    # 11. UNICODE NFC VS NFD DECOMPOSED DIACRITICS
    # ---------------------------------------------------------
    def test_14_unicode_nfc_and_nfd_accents_match(self):
        """Decomposed NFD Unicode (e.g. from MacOS or certain keyboards) matches precomposed NFC."""
        import unicodedata
        nfc_text = "Điện công nghiệp"
        nfd_text = unicodedata.normalize('NFD', nfc_text)

        self.assertNotEqual(nfc_text, nfd_text)  # Raw strings differ in byte representation
        self.assertEqual(normalize_text_token(nfc_text), normalize_text_token(nfd_text))
        self.assertEqual(normalize_text_token(nfd_text), "DIEN_CONG_NGHIEP")

    # ---------------------------------------------------------
    # 12. REVOKED CERTIFICATION EXCLUSION
    # ---------------------------------------------------------
    def test_15_revoked_certification_strict_exclusion(self):
        """Technician whose certification is marked revoked/expired is blocked."""
        catalog_with_revoked = dict(self.tenant_catalog)
        catalog_with_revoked['user_valid_certs'] = {
            'user-revoked': {
                'valid': set(),
                'expired': {'CERT_PCCC_CO_SO', 'CHUNG_CHI_PHONG_CHAY_CHUA_CHAY_CO_SO_CAP_2'}
            }
        }
        tech_user = MagicMock(id='user-revoked')
        tech_certs = ['CERT_PCCC_CO_SO']  # Still in legacy profile JSON

        # Must fail because catalog marks it revoked/expired
        self.assertFalse(is_certification_satisfied(
            'CERT_PCCC_CO_SO', tech_certs, tech_user=tech_user, catalog=catalog_with_revoked
        ))

    # ---------------------------------------------------------
    # 13. REAL-WORLD LOCATION: ENTERPRISE WITHOUT SPATIAL MAP
    # ---------------------------------------------------------
    def test_16_no_location_enterprise_zero_distance(self):
        """Enterprises without floor coordinates calculate 0.0 distance without crashing or false penalties."""
        # Both unconfigured (None)
        self.assertEqual(calculate_distance_score(None, None, 1, None, None, 1), 0.0)
        # Work order has no coordinates
        self.assertEqual(calculate_distance_score(20.0, 30.0, 1, None, None, 1), 0.0)
        # Tech has no coordinates
        self.assertEqual(calculate_distance_score(None, None, 1, 10.0, 15.0, 1), 0.0)
        # Default origin (0, 0) to (0, 0)
        self.assertEqual(calculate_distance_score(0.0, 0.0, 1, 0.0, 0.0, 1), 0.0)

    # ---------------------------------------------------------
    # 14. REAL-WORLD ZONES: VIETNAMESE ACCENT & FORMAT TOLERANCE
    # ---------------------------------------------------------
    def test_17_zone_penalty_vietnamese_accent_and_format_tolerance(self):
        """Technician and work order zone names match regardless of Vietnamese accents, casing, or hyphens."""
        # 'Xưởng 1' matches 'XUONG_1' -> 0 penalty
        self.assertEqual(calculate_zone_penalty("Xưởng 1", "XUONG_1"), 0.0)
        self.assertEqual(calculate_zone_penalty("xuong-1", "Xưởng 1"), 0.0)
        self.assertEqual(calculate_zone_penalty("Phân xưởng dập", "PHAN_XUONG_DAP"), 0.0)
        # Empty zones produce 0 penalty
        self.assertEqual(calculate_zone_penalty("", ""), 0.0)
        self.assertEqual(calculate_zone_penalty(None, None), 0.0)

    # ---------------------------------------------------------
    # 15. REAL-WORLD ZONES: GENERAL PLANT-WIDE / ROVING CREW
    # ---------------------------------------------------------
    def test_18_general_plant_wide_zone_zero_penalty(self):
        """Mobile roving crews or plant-wide tickets ('CHUNG', 'TOÀN NHÀ MÁY') incur 0 zone penalty."""
        self.assertEqual(calculate_zone_penalty("Chung", "Xưởng 1"), 0.0)
        self.assertEqual(calculate_zone_penalty("Toàn nhà máy", "Xưởng Đúc"), 0.0)
        self.assertEqual(calculate_zone_penalty("Đội cơ động", "Xưởng Lắp Ráp"), 0.0)
        self.assertEqual(calculate_zone_penalty("Xưởng 1", "Chung"), 0.0)

    # ---------------------------------------------------------
    # 16. REAL-WORLD ZONES: CONTROLLED & CLEANROOM STERILE AREAS
    # ---------------------------------------------------------
    def test_19_controlled_cleanroom_zone_penalty(self):
        """Entering sterile cleanrooms or bio-hazard areas incurs 40.0 gowning/decontamination penalty."""
        self.assertEqual(calculate_zone_penalty("Xưởng Cơ Khí", "Phòng Sạch Vi Sinh"), 40.0)
        self.assertEqual(calculate_zone_penalty("Xưởng 1", "ZONE_CLEANROOM"), 40.0)
        self.assertEqual(calculate_zone_penalty("Khu cách ly", "Xưởng 1"), 40.0)
        # Inside same cleanroom: 0 penalty
        self.assertEqual(calculate_zone_penalty("Phòng Sạch", "Phòng sạch"), 0.0)

    # ---------------------------------------------------------
    # 17. REAL-WORLD ZONES: DEDICATED WORKSHOPS (CROSS-ZONE TRANSIT)
    # ---------------------------------------------------------
    def test_20_different_workshops_penalty(self):
        """Technician assigned to Workshop A dispatching to Workshop B incurs standard 15.0 transit penalty."""
        self.assertEqual(calculate_zone_penalty("Xưởng Cơ Khí", "Xưởng Đúc"), 15.0)
        self.assertEqual(calculate_zone_penalty("ZONE_A", "ZONE_B"), 15.0)


if __name__ == '__main__':
    unittest.main()

