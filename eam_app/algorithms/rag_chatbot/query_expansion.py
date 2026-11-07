"""
Slang & Onomatopoeia Query Expansion Engine (Rule 2).
Transforms vernacular industrial terms and onomatopoeia into standardized technical keywords
to bridge the semantic distance gap in PGVector embeddings.
"""

from typing import Dict, Any, Optional, List
from .constants import SLANG_TECHNICAL_DICTIONARY


def expand_slang_query(prompt: str, asset_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Expands vernacular slang and onomatopoeic terms into technical equivalents.
    
    Args:
        prompt: Raw user query in Vietnamese.
        asset_context: Optional asset dictionary (e.g. {'model': 'PUMP-X100', 'manufactureYear': 2018}).
        
    Returns:
        dict: {
            'original_prompt': str,
            'expanded_query': str,
            'detected_slangs': List[str],
            'technical_additions': List[str]
        }
    """
    if not prompt or not isinstance(prompt, str):
        return {
            'original_prompt': '',
            'expanded_query': '',
            'detected_slangs': [],
            'technical_additions': []
        }

    lower_prompt = prompt.lower()
    detected_slangs: List[str] = []
    technical_additions: List[str] = []

    for slang, tech in SLANG_TECHNICAL_DICTIONARY.items():
        if slang in lower_prompt:
            detected_slangs.append(slang)
            for token in tech.split():
                if token not in technical_additions:
                    technical_additions.append(token)

    # Incorporate asset model if provided in context
    model_str = ""
    if asset_context:
        model = asset_context.get('model') or asset_context.get('applicable_model')
        if model and str(model).lower() not in lower_prompt:
            model_str = f" {model}"

    if technical_additions:
        expanded_query = f"{prompt.strip()} ({' '.join(technical_additions)}){model_str}".strip()
    else:
        expanded_query = f"{prompt.strip()}{model_str}".strip()

    return {
        'original_prompt': prompt,
        'expanded_query': expanded_query,
        'detected_slangs': detected_slangs,
        'technical_additions': technical_additions
    }
