"""
Multi-worker persistent safety configuration module.
Synchronizes custom slang technical dictionary and emergency hazard overrides
across multiple processes and Gunicorn workers via shared storage and last-modified checks.
"""

import json
import logging
import os
from typing import Optional, Dict, Any
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .constants import SLANG_TECHNICAL_DICTIONARY, EMERGENCY_HAZARDS

logger = logging.getLogger(__name__)

CONFIG_STORAGE_PATH = "config/assistant_safety_config.json"
_last_loaded_mtime = None


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
                    SLANG_TECHNICAL_DICTIONARY[str(k).lower().strip()] = str(v).strip()
            if isinstance(data.get('emergencyHazards'), dict):
                for k, v in data['emergencyHazards'].items():
                    if isinstance(v, dict) and 'keywords' in v:
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
        data.setdefault("slangDictionary", {}).update({str(k).lower().strip(): str(v).strip() for k, v in custom_slang.items()})
    if custom_hazards and isinstance(custom_hazards, dict):
        data.setdefault("emergencyHazards", {}).update({k: v for k, v in custom_hazards.items() if isinstance(v, dict) and 'keywords' in v})

    # Update in-memory dicts
    if isinstance(data.get('slangDictionary'), dict):
        for k, v in data['slangDictionary'].items():
            SLANG_TECHNICAL_DICTIONARY[str(k).lower().strip()] = str(v).strip()
    if isinstance(data.get('emergencyHazards'), dict):
        for k, v in data['emergencyHazards'].items():
            if isinstance(v, dict) and 'keywords' in v:
                EMERGENCY_HAZARDS[k] = v

    content_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')

    # Atomic write to avoid race condition where another worker reads a deleted/half-written file
    written_via_fs = False
    try:
        if hasattr(default_storage, 'path'):
            full_path = default_storage.path(CONFIG_STORAGE_PATH)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            tmp_path = full_path + f".tmp.{os.getpid()}"
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
