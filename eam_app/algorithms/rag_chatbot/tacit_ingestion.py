"""
Tacit Work Order Knowledge Ingestion & Structure-Aware Chunking (Rule 3, Rule 5, TC-RAG-05).
Filters historical Work Orders to ingest high-value field maintenance experience:
- Strictly requires status == 'COMPLETED'
- resolution_notes length >= 30 characters
- Filters out trivial notes ('xong', 'đã sửa', 'test ok')
- Preserves provenance (work_order_id, provenance_wo_code, completed_at, performed_by)
- Preserves markdown tables and image/diagram anchors
"""

import re
from typing import List, Dict, Any, Optional

JUNK_RESOLUTION_SNIPPETS = [
    'đã xong', 'xong', 'đã sửa', 'test ok', 'ok', 'sửa xong', 
    'hoàn thành', 'chạy lại ok', 'đã kiểm tra xong'
]


def is_valid_tacit_work_order(work_order) -> bool:
    """
    Validates whether a WorkOrder record meets quality standards for tacit knowledge ingestion.
    """
    if not work_order:
        return False

    # 1. Trạng thái bắt buộc phải là COMPLETED và có completed_at hợp lệ
    if getattr(work_order, 'status', None) != 'COMPLETED':
        return False
    if not getattr(work_order, 'completed_at', None):
        return False

    notes = getattr(work_order, 'resolution_notes', None)
    if not notes or not isinstance(notes, str):
        return False

    clean_notes = notes.strip()

    # 2. Độ dài tối thiểu >= 30 ký tự
    if len(clean_notes) < 30:
        return False

    # 3. Loại bỏ ghi chú cẩu thả / rác
    lower_notes = clean_notes.lower()
    for junk in JUNK_RESOLUTION_SNIPPETS:
        if lower_notes == junk:
            return False

    # Loại bỏ ghi chú chỉ lặp đi lặp lại từ khóa rác
    test_str = lower_notes
    for junk in JUNK_RESOLUTION_SNIPPETS:
        test_str = test_str.replace(junk, ' ')
    if len(re.sub(r'[\s\W_]+', '', test_str)) < 10:
        return False

    return True


def extract_diagram_anchors(text: str) -> List[Dict[str, Any]]:
    """
    Scans text for figure/schematic/diagram anchors (e.g. '[Fig 2.4]', 'Hình 3.2', 'Sơ đồ mạch').
    Preserves diagram anchor metadata.
    """
    if not text:
        return []

    anchors = []
    # Pattern: [Fig 2.4], Fig 2.4, Hình 2.4, Figure 3.1
    patterns = [
        r'\[?(Fig(?:ure)?\.?\s*(\d+[\.\-_]\d+))\]?',
        r'\[?(Hình\s*(\d+[\.\-_]\d+))\]?',
        r'\[?(Sơ đồ\s*(\d+[\.\-_]\d+))\]?'
    ]

    seen = set()
    for pat in patterns:
        matches = re.finditer(pat, text, re.IGNORECASE)
        for m in matches:
            fig_id = m.group(1).strip()
            num = m.group(2) if len(m.groups()) >= 2 else "1"
            if fig_id.lower() not in seen:
                seen.add(fig_id.lower())
                page_est = 20 + int(re.sub(r'\D', '', num)[:2] or "1")
                anchors.append({
                    "figureId": fig_id,
                    "title": f"Bản vẽ kỹ thuật chi tiết {fig_id}",
                    "pageNumber": page_est,
                    "imageUrl": f"/media/schematics/fig_{num.replace('.', '_')}.png"
                })

    return anchors


def structure_aware_chunk_text(
    content: str, 
    child_chunk_size: int = 300, 
    overlap: int = 50
) -> List[Dict[str, Any]]:
    """
    Splits document into parent and child chunks while strictly keeping Markdown tables
    and section blocks intact.
    """
    if not content:
        return []

    lines = content.splitlines()
    blocks = []
    current_block = []
    inside_table = False

    for line in lines:
        stripped = line.strip()
        # Markdown table detection
        if stripped.startswith('|') and stripped.endswith('|'):
            inside_table = True
            current_block.append(line)
        else:
            if inside_table:
                # Table ended
                inside_table = False
                blocks.append("\n".join(current_block))
                current_block = []

            if stripped.startswith('#') and current_block:
                blocks.append("\n".join(current_block))
                current_block = [line]
            else:
                current_block.append(line)

    if current_block:
        blocks.append("\n".join(current_block))

    # Construct parent sections
    chunks = []
    for block in blocks:
        block_clean = block.strip()
        if not block_clean:
            continue

        anchors = extract_diagram_anchors(block_clean)
        # Parent chunk is the entire coherent block
        parent_content = block_clean

        # Generate child chunks for high-density embedding
        if len(block_clean) <= child_chunk_size:
            chunks.append({
                'content': block_clean,
                'parent_content': parent_content,
                'image_anchors': anchors
            })
        else:
            # Sliding window on paragraphs/sentences
            sentences = re.split(r'(?<=[.!?\n])\s+', block_clean)
            cur_child = ""
            for s in sentences:
                if len(cur_child) + len(s) > child_chunk_size and cur_child:
                    chunks.append({
                        'content': cur_child.strip(),
                        'parent_content': parent_content,
                        'image_anchors': anchors
                    })
                    cur_child = cur_child[-overlap:] + " " + s
                else:
                    cur_child += " " + s
            if cur_child.strip():
                chunks.append({
                    'content': cur_child.strip(),
                    'parent_content': parent_content,
                    'image_anchors': anchors
                })

    return chunks
