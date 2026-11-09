"""
Multi-worker persistent safety configuration module.
Synchronizes custom slang technical dictionary and emergency hazard overrides
across multiple processes and Gunicorn workers via shared storage and last-modified checks.
"""

import json
import logging
import os
import uuid
from typing import Optional, Dict, Any, Tuple
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .constants import SLANG_TECHNICAL_DICTIONARY, EMERGENCY_HAZARDS

logger = logging.getLogger(__name__)

CONFIG_STORAGE_PATH = "config/assistant_safety_config.json"
_last_loaded_mtime = None


def validate_hazard_payload(custom_hazards: Any) -> Tuple[bool, Optional[str], Dict[str, Dict[str, Any]]]:
    """
    Validates that each emergency hazard conforms to the required schema expected by Safety Classifier:
    - code (str non-empty)
    - name (str non-empty)
    - instruction (str non-empty)
    - action_summary (str non-empty)
    - keywords (non-empty list of non-empty strings)
    """
    if not isinstance(custom_hazards, dict):
        return False, "Cấu hình nguy cơ khẩn cấp (emergencyHazards) phải là một dictionary (object).", {}

    cleaned = {}
    for h_code, h_body in custom_hazards.items():
        if not isinstance(h_code, str) or not h_code.strip():
            return False, f"Mã nguy cơ '{h_code}' không hợp lệ. Phải là chuỗi ký tự không rỗng.", {}

        if not isinstance(h_body, dict):
            return False, f"Cấu hình cho nguy cơ '{h_code}' phải là một dictionary.", {}

        # Required fields check
        for field in ('name', 'instruction', 'action_summary'):
            val = h_body.get(field)
            if not isinstance(val, str) or not val.strip():
                return False, f"Nguy cơ '{h_code}' thiếu hoặc có trường '{field}' không hợp lệ (phải là chuỗi không rỗng).", {}

        keywords = h_body.get('keywords')
        if not isinstance(keywords, list) or len(keywords) == 0:
            return False, f"Nguy cơ '{h_code}' phải có danh sách từ khóa 'keywords' chứa ít nhất 1 từ khóa.", {}

        cleaned_kw = []
        for kw in keywords:
            if not isinstance(kw, str) or not kw.strip():
                return False, f"Từ khóa '{kw}' trong nguy cơ '{h_code}' không hợp lệ (phải là chuỗi ký tự không rỗng).", {}
            cleaned_kw.append(kw.lower().strip())

        cleaned[h_code.strip()] = {
            'name': h_body['name'].strip(),
            'instruction': h_body['instruction'].strip(),
            'action_summary': h_body['action_summary'].strip(),
            'keywords': cleaned_kw,
        }

    return True, None, cleaned


def validate_slang_payload(custom_slang: Any) -> Tuple[bool, Optional[str], Dict[str, str]]:
    """
    Validates slang technical dictionary entries (non-empty string key and value).
    """
    if not isinstance(custom_slang, dict):
        return False, "Từ điển tiếng lóng (slangDictionary) phải là một dictionary.", {}
    cleaned = {}
    for k, v in custom_slang.items():
        if not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip():
            return False, f"Thuật ngữ tiếng lóng '{k}: {v}' không hợp lệ (phải là chuỗi ký tự không rỗng).", {}
        cleaned[k.lower().strip()] = v.strip()
    return True, None, cleaned


def load_persisted_safety_config(force: bool = False) -> bool:
    """
    Loads persisted custom slang and emergency hazard overrides from storage into memory.
    If force=False, only reloads when the file mtime has changed since last load.
    Returns True if reloaded, False otherwise.
    """
    global _last_loaded_mtime
    try:
        if not default_storage.exists(CONFIG_STORAGE_PATH):
            return False

        try:
            mtime = default_storage.get_modified_time(CONFIG_STORAGE_PATH)
        except Exception:
            mtime = None

        if not force and _last_loaded_mtime is not None and mtime is not None and mtime == _last_loaded_mtime:
            return False

        with default_storage.open(CONFIG_STORAGE_PATH, 'r') as f:
            raw = f.read()
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            data = json.loads(raw)
            if isinstance(data.get('slangDictionary'), dict):
                for k, v in data['slangDictionary'].items():
                    if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
                        SLANG_TECHNICAL_DICTIONARY[k.lower().strip()] = v.strip()
            if isinstance(data.get('emergencyHazards'), dict):
                for k, v in data['emergencyHazards'].items():
                    if (isinstance(v, dict) and
                        isinstance(v.get('keywords'), list) and
                        v.get('name') and v.get('instruction') and v.get('action_summary')):
                        EMERGENCY_HAZARDS[k] = v

        _last_loaded_mtime = mtime
        return True
    except Exception as e:
        logger.warning("Failed to load persisted safety config: %s", e)
        return False


def ensure_safety_config_loaded() -> None:
    """Lightweight check to ensure memory contains latest configuration from shared storage."""
    load_persisted_safety_config(force=False)


def save_persisted_safety_config(custom_slang: Optional[Dict[str, str]] = None, custom_hazards: Optional[Dict[str, Any]] = None) -> None:
    """
    Saves updated custom slang and emergency hazards to persistent storage and updates memory.
    Ensures validated structure and thread-safe atomic file replacement.
    """
    global _last_loaded_mtime
    data = {"slangDictionary": {}, "emergencyHazards": {}}
    if default_storage.exists(CONFIG_STORAGE_PATH):
        try:
            with default_storage.open(CONFIG_STORAGE_PATH, 'r') as f:
                raw = f.read()
                if isinstance(raw, bytes):
                    raw = raw.decode('utf-8')
                data = json.loads(raw)
        except Exception:
            pass

    if custom_slang and isinstance(custom_slang, dict):
        valid_slang, _, cleaned_s = validate_slang_payload(custom_slang)
        if valid_slang:
            data.setdefault("slangDictionary", {}).update(cleaned_s)
    if custom_hazards and isinstance(custom_hazards, dict):
        valid_h, _, cleaned_h = validate_hazard_payload(custom_hazards)
        if valid_h:
            data.setdefault("emergencyHazards", {}).update(cleaned_h)

    content_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')

    # Atomic write to avoid race condition where another worker reads a deleted/half-written file
    written_via_fs = False
    try:
        if hasattr(default_storage, 'path'):
            full_path = default_storage.path(CONFIG_STORAGE_PATH)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            tmp_path = full_path + f".tmp.{os.getpid()}.{uuid.uuid4().hex}"
            with open(tmp_path, 'wb') as f_tmp:
                f_tmp.write(content_bytes)
                f_tmp.flush()
                os.fsync(f_tmp.fileno())
            os.replace(tmp_path, full_path)
            written_via_fs = True
    except Exception as e:
        logger.debug("Filesystem atomic replace not applicable: %s", e)

    if not written_via_fs:
        if default_storage.exists(CONFIG_STORAGE_PATH):
            default_storage.delete(CONFIG_STORAGE_PATH)
        default_storage.save(CONFIG_STORAGE_PATH, ContentFile(content_bytes))

    try:
        _last_loaded_mtime = default_storage.get_modified_time(CONFIG_STORAGE_PATH)
    except Exception:
        _last_loaded_mtime = None

    # Update in-memory dicts ONLY after successful persistent write (Atomicity guarantee)
    if isinstance(data.get('slangDictionary'), dict):
        for k, v in data['slangDictionary'].items():
            if isinstance(k, str) and isinstance(v, str):
                SLANG_TECHNICAL_DICTIONARY[k.lower().strip()] = v.strip()
    if isinstance(data.get('emergencyHazards'), dict):
        for k, v in data['emergencyHazards'].items():
            if (isinstance(v, dict) and
                isinstance(v.get('keywords'), list) and
                v.get('name') and v.get('instruction') and v.get('action_summary')):
                EMERGENCY_HAZARDS[k] = v
