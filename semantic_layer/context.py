"""Load semantic model context for Spagent AI queries."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from semantic_layer.config import SEMANTIC_OUTPUT_DIR, load_semantic_config

logger = logging.getLogger(__name__)


def semantic_model_exists() -> bool:
    cfg = load_semantic_config()
    path = os.path.join(SEMANTIC_OUTPUT_DIR, f'{cfg.model_name}.json')
    return os.path.exists(path)


def load_semantic_json() -> Optional[Dict[str, Any]]:
    """Load the generated JSON metadata if it exists."""
    cfg = load_semantic_config()
    path = os.path.join(SEMANTIC_OUTPUT_DIR, f'{cfg.model_name}.json')
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as exc:
        logger.warning('Failed to load semantic model: %s', exc)
        return None


def semantic_context_for_llm(max_entities: int = 15, max_measures: int = 10) -> str:
    """Compact semantic layer text for LLM SQL generation."""
    data = load_semantic_json()
    if not data:
        return ''

    lines = ['Semantic layer (business definitions):']

    entities = data.get('entities') or []
    for ent in entities[:max_entities]:
        name = ent.get('business_name') or ent.get('name', '')
        table = ent.get('source_table', '')
        etype = ent.get('entity_type', '')
        pk = ent.get('primary_key') or []
        syns = ent.get('synonyms') or []
        syn_txt = f', synonyms: {", ".join(syns[:3])}' if syns else ''
        pk_txt = f', PK: {", ".join(pk)}' if pk else ''
        lines.append(f'- Entity "{name}" ({etype}) → table {table}{pk_txt}{syn_txt}')

    dimensions = data.get('dimensions') or []
    conformed = [d for d in dimensions if d.get('is_conformed')]
    if conformed:
        lines.append('Conformed dimensions:')
        for dim in conformed[:8]:
            lines.append(
                f'  - {dim.get("business_name")} ({dim.get("source_table")}.{dim.get("source_column")})'
            )

    measures = data.get('measures') or []
    if measures:
        lines.append('Business measures:')
        for m in measures[:max_measures]:
            lines.append(
                f'  - {m.get("business_name")}: {m.get("expression")} on {m.get("source_table")}'
            )

    relationships = data.get('relationships') or []
    if relationships:
        lines.append('Relationships:')
        for rel in relationships[:10]:
            lines.append(
                f'  - {rel.get("from_table")}.{rel.get("from_column")} → '
                f'{rel.get("to_table")}.{rel.get("to_column")} '
                f'({rel.get("relationship_type")}, confidence {rel.get("confidence", 0):.0%})'
            )

    return '\n'.join(lines)


def build_semantic_summary() -> Dict[str, Any]:
    """Lightweight summary for the Spagent AI UI."""
    cfg = load_semantic_config()
    data = load_semantic_json()

    if not data:
        return {
            'built': False,
            'model_name': cfg.model_name,
            'model_description': cfg.model_description,
            'entities': 0,
            'dimensions': 0,
            'facts': 0,
            'measures': 0,
            'relationships': 0,
            'sources': [],
            'entity_samples': [],
            'measure_samples': [],
            'suggested_questions': _default_questions(),
        }

    entities = data.get('entities') or []
    measures = data.get('measures') or []
    source_info = data.get('source') or {}

    entity_samples = [
        {
            'name': e.get('name'),
            'business_name': e.get('business_name'),
            'entity_type': e.get('entity_type'),
            'source_table': e.get('source_table'),
        }
        for e in entities[:8]
    ]

    measure_samples = [
        {
            'name': m.get('name'),
            'business_name': m.get('business_name'),
            'expression': m.get('expression'),
            'source_table': m.get('source_table'),
        }
        for m in measures[:8]
    ]

    return {
        'built': True,
        'model_name': source_info.get('model_name') or cfg.model_name,
        'model_description': cfg.model_description,
        'entities': len(entities),
        'dimensions': len(data.get('dimensions') or []),
        'facts': len(data.get('facts') or []),
        'measures': len(measures),
        'relationships': len(data.get('relationships') or []),
        'sources': source_info.get('sources') or [],
        'entity_samples': entity_samples,
        'measure_samples': measure_samples,
        'suggested_questions': _suggested_questions(entities, measures),
    }


def _suggested_questions(entities: List[Dict], measures: List[Dict]) -> List[str]:
    questions: List[str] = []

    for m in measures[:4]:
        biz = m.get('business_name') or m.get('name', '')
        if biz:
            questions.append(f'What is the {biz.lower()}?')

    for e in entities[:3]:
        biz = e.get('business_name') or e.get('name', '')
        table = e.get('source_table', '')
        if biz and table:
            questions.append(f'Show me all {biz.lower()} records')

    if not questions:
        return _default_questions()

    questions.extend(_default_questions()[:2])
    return questions[:6]


def _default_questions() -> List[str]:
    return [
        'How many contacts do we have?',
        'Which patients have not visited in 90 days?',
        'What are our open opportunities?',
        'Show contacts with unread conversations',
    ]
