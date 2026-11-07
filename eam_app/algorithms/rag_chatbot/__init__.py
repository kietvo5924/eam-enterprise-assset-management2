"""
Task 11.9: Intelligent AI Assistant / Chatbot (RAG & Sentence-Transformers).
Self-contained research algorithms package.
"""

from .safety_classifier import classify_safety_context
from .query_expansion import expand_slang_query
from .vector_engine import (
    embed_text, 
    retrieve_relevant_chunks, 
    classify_similarity_tier,
    get_embedding_model
)
from .contradiction_guard import check_negation_contradiction
from .inventory_interlock import check_live_inventory
from .offline_pack import generate_offline_package
from .tacit_ingestion import (
    is_valid_tacit_work_order, 
    extract_diagram_anchors, 
    structure_aware_chunk_text
)
from .ollama_client import OllamaClient
from .pipeline import process_rag_query

__all__ = [
    'classify_safety_context',
    'expand_slang_query',
    'embed_text',
    'retrieve_relevant_chunks',
    'classify_similarity_tier',
    'get_embedding_model',
    'check_negation_contradiction',
    'check_live_inventory',
    'generate_offline_package',
    'is_valid_tacit_work_order',
    'extract_diagram_anchors',
    'structure_aware_chunk_text',
    'OllamaClient',
    'process_rag_query',
]
