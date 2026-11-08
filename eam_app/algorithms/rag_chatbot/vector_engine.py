"""
Sentence-Transformers Embedding & Multi-Source PGVector Query Engine (Rule 2, 4, 5, 10).
- Uses paraphrase-multilingual-MiniLM-L12-v2 (384 dimensions)
- Executes raw PGVector queries with cosine distance operator <=>
- Supports Parent-Child retrieval (match on child, return full parent section)
- Implements hybrid multi-tenancy:
    * Equipment knowledge strictly isolated by tenant_id
    * System software guides (is_system_guide=True, tenant_id=NULL) retrieved globally via LEFT JOIN
- Enforces granular model and manufacture year filtering
"""

import json
import logging
from typing import List, Dict, Any, Optional
from django.db import connection
from sentence_transformers import SentenceTransformer
from .constants import (
    DEFAULT_MODEL_NAME,
    EMBEDDING_DIMENSION,
    SIMILARITY_THRESHOLD_FALLBACK,
    SIMILARITY_THRESHOLD_HIGH,
    SAFE_FALLBACK_MESSAGE,
    MEDIUM_CONFIDENCE_WARNING,
)

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    """Loads and caches the multilingual SentenceTransformer model."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        try:
            logger.info("Loading SentenceTransformer model %s...", DEFAULT_MODEL_NAME)
            _EMBEDDING_MODEL = SentenceTransformer(DEFAULT_MODEL_NAME)
        except Exception as e:
            logger.error("Failed to load model %s: %s", DEFAULT_MODEL_NAME, str(e))
            raise
    return _EMBEDDING_MODEL


def embed_text(text: str) -> List[float]:
    """
    Computes a 384-dimensional dense semantic embedding vector.
    """
    if not text:
        return [0.0] * EMBEDDING_DIMENSION
    model = get_embedding_model()
    vec = model.encode(text, convert_to_numpy=True)
    return vec.tolist()


def embed_texts(texts: List[str], batch_size: int = 64) -> List[List[float]]:
    """
    Computes 384-dimensional dense semantic embedding vectors for a batch of texts.
    """
    if not texts:
        return []
    model = get_embedding_model()
    # Normalize empty strings to avoid errors
    safe_texts = [t if t else " " for t in texts]
    vecs = model.encode(safe_texts, batch_size=batch_size, convert_to_numpy=True)
    return vecs.tolist()


def format_vector_for_sql(vector: List[float]) -> str:
    """Formats a list of floats into a PostgreSQL vector string '[0.1, 0.2, ...]'."""
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"


def retrieve_relevant_chunks(
    query_text: str,
    tenant_id: Optional[str] = None,
    asset_model: Optional[str] = None,
    manufacture_year: Optional[int] = None,
    serial_number: Optional[str] = None,
    is_system_query: bool = False,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Dual-stream PGVector retrieval using Cosine Distance (<=>).
    Returns list of matched chunks with full parent_content, metadata, and similarity score.
    Strictly filters by tenant_id, asset_model, manufacture_year, and serial_number across
    OEM Manuals, Tacit Work Orders, and Curated QA.
    """
    query_vec = embed_text(query_text)
    vec_str = format_vector_for_sql(query_vec)

    results: List[Dict[str, Any]] = []

    with connection.cursor() as cursor:
        if is_system_query:
            # Nhánh 2: Tri thức Hướng dẫn Hệ thống Toàn cục (Global System Guides)
            if tenant_id:
                sql = """
                    SELECT dc.id, dc.content, dc.parent_content, dc.image_anchors, dc.source_type,
                           dc.provenance_wo_code, td.title, 1 - (dc.embedding <=> %s::vector) AS similarity,
                           dc.is_system_guide, dc.page_number
                    FROM document_chunks dc
                    LEFT JOIN technical_documents td ON dc.document_id = td.id
                    WHERE dc.is_active = TRUE
                      AND dc.is_system_guide = TRUE
                      AND (dc.tenant_id IS NULL OR dc.tenant_id = %s)
                    ORDER BY dc.embedding <=> %s::vector
                    LIMIT %s;
                """
                cursor.execute(sql, [vec_str, tenant_id, vec_str, limit])
            else:
                sql = """
                    SELECT dc.id, dc.content, dc.parent_content, dc.image_anchors, dc.source_type,
                           dc.provenance_wo_code, td.title, 1 - (dc.embedding <=> %s::vector) AS similarity,
                           dc.is_system_guide, dc.page_number
                    FROM document_chunks dc
                    LEFT JOIN technical_documents td ON dc.document_id = td.id
                    WHERE dc.is_active = TRUE
                      AND dc.is_system_guide = TRUE
                    ORDER BY dc.embedding <=> %s::vector
                    LIMIT %s;
                """
                cursor.execute(sql, [vec_str, vec_str, limit])
        else:
            # Nhánh 1: Tri thức Thiết bị & Nhà xưởng (Tenant-Isolated)
            # Lọc linh hoạt theo tenant_id, model, dải năm sản xuất và serial nếu có
            if tenant_id:
                sql = """
                    SELECT dc.id, dc.content, dc.parent_content, dc.image_anchors, dc.source_type,
                           dc.provenance_wo_code, td.title, 1 - (dc.embedding <=> %s::vector) AS similarity,
                           dc.is_system_guide, dc.page_number
                    FROM document_chunks dc
                    LEFT JOIN technical_documents td ON dc.document_id = td.id
                    LEFT JOIN work_orders w ON dc.work_order_id = w.id
                    LEFT JOIN assets a ON w.asset_id = a.id
                    WHERE dc.is_active = TRUE
                      AND (dc.tenant_id = %s OR (dc.is_system_guide = TRUE AND dc.tenant_id IS NULL))
                      AND (
                          -- Luồng 1: Sổ tay OEM khớp Model và dải năm (+ serial prefix nếu có)
                          (
                              dc.source_type = 'OEM_MANUAL'
                              AND (%s IS NULL OR td.applicable_model IS NULL OR td.applicable_model = %s)
                              AND (%s IS NULL OR %s BETWEEN COALESCE(td.applicable_year_start, 1900) AND COALESCE(td.applicable_year_end, 2100))
                              AND (%s IS NULL OR td.serial_number_prefix IS NULL OR td.serial_number_prefix = '' OR %s LIKE CONCAT(td.serial_number_prefix, '%%'))
                          )
                          OR
                          -- Luồng 2: Tri thức ngầm từ Work Order COMPLETED đã kiểm định (khớp Model & Serial của Asset)
                          (
                              dc.source_type = 'TACIT_WORK_ORDER'
                              AND dc.is_verified_tacit = TRUE
                              AND (%s IS NULL OR a.model IS NULL OR a.model = %s)
                              AND (%s IS NULL OR a.serial_number IS NULL OR a.serial_number = %s)
                              AND (%s IS NULL OR a.purchase_date IS NULL OR EXTRACT(YEAR FROM a.purchase_date) = %s)
                          )
                          OR
                          -- Luồng 3: Tri thức hỏi đáp chuẩn mực đã phê duyệt (khớp Model và dải năm, dùng EXISTS để triệt tiêu trùng lặp)
                          (
                              dc.source_type = 'CURATED_QA'
                              AND (
                                  NOT EXISTS (
                                      SELECT 1 FROM curated_qa_knowledge cqa_check
                                      WHERE (dc.content = cqa_check.question_pattern OR dc.parent_content = cqa_check.gold_answer)
                                        AND (cqa_check.tenant_id = dc.tenant_id OR (cqa_check.is_system_guide = TRUE AND dc.is_system_guide = TRUE))
                                  )
                                  OR EXISTS (
                                      SELECT 1 FROM curated_qa_knowledge cqa
                                      WHERE (dc.content = cqa.question_pattern OR dc.parent_content = cqa.gold_answer)
                                        AND (cqa.tenant_id = dc.tenant_id OR (cqa.is_system_guide = TRUE AND dc.is_system_guide = TRUE))
                                        AND (%s IS NULL OR cqa.applicable_model IS NULL OR cqa.applicable_model = '' OR cqa.applicable_model = %s)
                                        AND (%s IS NULL OR %s BETWEEN COALESCE(cqa.applicable_year_start, 1900) AND COALESCE(cqa.applicable_year_end, 2100))
                                  )
                              )
                          )
                          OR
                          -- Luồng 4: Hướng dẫn hệ thống
                          (dc.source_type = 'SYSTEM_GUIDE' OR dc.is_system_guide = TRUE)
                      )
                    ORDER BY dc.embedding <=> %s::vector
                    LIMIT %s;
                """
                cursor.execute(sql, [
                    vec_str, tenant_id,
                    asset_model, asset_model,
                    manufacture_year, manufacture_year,
                    serial_number, serial_number,
                    asset_model, asset_model,
                    serial_number, serial_number,
                    manufacture_year, manufacture_year,
                    asset_model, asset_model,
                    manufacture_year, manufacture_year,
                    vec_str, limit
                ])
            else:
                sql = """
                    SELECT dc.id, dc.content, dc.parent_content, dc.image_anchors, dc.source_type,
                           dc.provenance_wo_code, td.title, 1 - (dc.embedding <=> %s::vector) AS similarity,
                           dc.is_system_guide, dc.page_number
                    FROM document_chunks dc
                    LEFT JOIN technical_documents td ON dc.document_id = td.id
                    LEFT JOIN work_orders w ON dc.work_order_id = w.id
                    LEFT JOIN assets a ON w.asset_id = a.id
                    WHERE dc.is_active = TRUE
                      AND (
                          -- Luồng 1: Sổ tay OEM khớp Model và dải năm (+ serial prefix nếu có)
                          (
                              dc.source_type = 'OEM_MANUAL'
                              AND (%s IS NULL OR td.applicable_model IS NULL OR td.applicable_model = %s)
                              AND (%s IS NULL OR %s BETWEEN COALESCE(td.applicable_year_start, 1900) AND COALESCE(td.applicable_year_end, 2100))
                              AND (%s IS NULL OR td.serial_number_prefix IS NULL OR td.serial_number_prefix = '' OR %s LIKE CONCAT(td.serial_number_prefix, '%%'))
                          )
                          OR
                          -- Luồng 2: Tri thức ngầm từ Work Order COMPLETED đã kiểm định
                          (
                              dc.source_type = 'TACIT_WORK_ORDER'
                              AND dc.is_verified_tacit = TRUE
                              AND (%s IS NULL OR a.model IS NULL OR a.model = %s)
                              AND (%s IS NULL OR a.serial_number IS NULL OR a.serial_number = %s)
                              AND (%s IS NULL OR a.purchase_date IS NULL OR EXTRACT(YEAR FROM a.purchase_date) = %s)
                          )
                          OR
                          -- Luồng 3: Tri thức hỏi đáp chuẩn mực đã phê duyệt (khớp Model và dải năm, dùng EXISTS để triệt tiêu trùng lặp)
                          (
                              dc.source_type = 'CURATED_QA'
                              AND (
                                  NOT EXISTS (
                                      SELECT 1 FROM curated_qa_knowledge cqa_check
                                      WHERE (dc.content = cqa_check.question_pattern OR dc.parent_content = cqa_check.gold_answer)
                                        AND (cqa_check.tenant_id = dc.tenant_id OR (cqa_check.is_system_guide = TRUE AND dc.is_system_guide = TRUE))
                                  )
                                  OR EXISTS (
                                      SELECT 1 FROM curated_qa_knowledge cqa
                                      WHERE (dc.content = cqa.question_pattern OR dc.parent_content = cqa.gold_answer)
                                        AND (cqa.tenant_id = dc.tenant_id OR (cqa.is_system_guide = TRUE AND dc.is_system_guide = TRUE))
                                        AND (%s IS NULL OR cqa.applicable_model IS NULL OR cqa.applicable_model = '' OR cqa.applicable_model = %s)
                                        AND (%s IS NULL OR %s BETWEEN COALESCE(cqa.applicable_year_start, 1900) AND COALESCE(cqa.applicable_year_end, 2100))
                                  )
                              )
                          )
                          OR
                          -- Luồng 4: Hướng dẫn hệ thống
                          (dc.source_type = 'SYSTEM_GUIDE' OR dc.is_system_guide = TRUE)
                      )
                    ORDER BY dc.embedding <=> %s::vector
                    LIMIT %s;
                """
                cursor.execute(sql, [
                    vec_str,
                    asset_model, asset_model,
                    manufacture_year, manufacture_year,
                    serial_number, serial_number,
                    asset_model, asset_model,
                    serial_number, serial_number,
                    manufacture_year, manufacture_year,
                    asset_model, asset_model,
                    manufacture_year, manufacture_year,
                    vec_str, limit
                ])

        rows = cursor.fetchall()
        for row in rows:
            chunk_id, content, parent_content, image_anchors, source_type, prov_code, doc_title, sim, is_sys, page_num = row
            
            # Parse image_anchors json if string
            anchors_val = image_anchors
            if isinstance(image_anchors, str):
                try:
                    anchors_val = json.loads(image_anchors)
                except Exception:
                    anchors_val = []

            results.append({
                'id': str(chunk_id),
                'content': content,
                'parent_content': parent_content,
                'image_anchors': anchors_val or [],
                'source_type': source_type,
                'provenance_wo_code': prov_code,
                'document_title': doc_title or "Tài liệu kỹ thuật",
                'similarity': float(sim) if sim is not None else 0.0,
                'is_system_guide': bool(is_sys),
                'page_number': page_num or 1
            })

    return results


def classify_similarity_tier(score: float) -> Dict[str, Any]:
    """
    Maps a similarity score to the 3 enterprise relevance tiers:
    - Sim < 0.65: LOW_CONFIDENCE (Safe Fallback)
    - 0.65 <= Sim < 0.75: MEDIUM_CONFIDENCE (Amber warning)
    - Sim >= 0.75: HIGH_CONFIDENCE (Green confident match)
    """
    if score < SIMILARITY_THRESHOLD_FALLBACK:
        return {
            'tier': 'LOW_CONFIDENCE',
            'score': round(score, 3),
            'tierLabel': f"Độ tương đồng thấp ({round(score * 100, 1)}%) — Không đủ độ tin cậy",
            'isFallback': True,
            'warning': SAFE_FALLBACK_MESSAGE
        }
    elif score < SIMILARITY_THRESHOLD_HIGH:
        return {
            'tier': 'MEDIUM_CONFIDENCE',
            'score': round(score, 3),
            'tierLabel': f"Độ tương đồng trung bình ({round(score * 100, 1)}%)",
            'isFallback': False,
            'warning': MEDIUM_CONFIDENCE_WARNING
        }
    else:
        return {
            'tier': 'HIGH_CONFIDENCE',
            'score': round(score, 3),
            'tierLabel': f"Độ tương đồng cao ({round(score * 100, 1)}%)",
            'isFallback': False,
            'warning': None
        }
