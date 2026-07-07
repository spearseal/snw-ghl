"""YAML semantic definition generator."""
from __future__ import annotations

from typing import Any, Dict, List

import yaml

from semantic_layer.models import SemanticModel


def generate_yaml(model: SemanticModel) -> str:
    """Generate governed YAML semantic definitions."""
    doc: Dict[str, Any] = {
        'model': {
            'name': model.name,
            'description': model.description,
            'version': model.version,
            'sources': model.sources,
        },
        'entities': [_entity_yaml(e) for e in model.entities],
        'dimensions': [_dimension_yaml(d) for d in model.dimensions],
        'facts': [_fact_yaml(f) for f in model.facts],
        'measures': [_measure_yaml(m) for m in model.measures],
        'relationships': [_relationship_yaml(r) for r in model.relationships],
        'hierarchies': [_hierarchy_yaml(h) for h in model.hierarchies],
    }
    return yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _entity_yaml(e) -> Dict[str, Any]:
    return {
        'name': e.name,
        'business_name': e.business_name,
        'description': e.description,
        'source_table': e.source_table,
        'entity_type': e.entity_type.value,
        'primary_key': e.primary_key,
        'synonyms': e.synonyms,
    }


def _dimension_yaml(d) -> Dict[str, Any]:
    return {
        'name': d.name,
        'business_name': d.business_name,
        'description': d.description,
        'source_table': d.source_table,
        'source_column': d.source_column,
        'data_type': d.data_type,
        'semantic': d.semantic.value,
        'is_conformed': d.is_conformed,
        'synonyms': d.synonyms,
    }


def _fact_yaml(f) -> Dict[str, Any]:
    return {
        'name': f.name,
        'business_name': f.business_name,
        'description': f.description,
        'source_table': f.source_table,
        'grain': f.grain,
        'dimensions': f.dimensions,
        'measures': f.measures,
    }


def _measure_yaml(m) -> Dict[str, Any]:
    return {
        'name': m.name,
        'business_name': m.business_name,
        'description': m.description,
        'expression': m.expression,
        'aggregation': m.aggregation,
        'source_table': m.source_table,
        'source_column': m.source_column,
        'format': m.format,
    }


def _relationship_yaml(r) -> Dict[str, Any]:
    return {
        'name': r.name,
        'from_entity': r.from_entity,
        'to_entity': r.to_entity,
        'from_column': r.from_column,
        'to_column': r.to_column,
        'relationship_type': r.relationship_type.value,
        'confidence': r.confidence,
    }


def _hierarchy_yaml(h) -> Dict[str, Any]:
    return {
        'name': h.name,
        'dimension': h.dimension,
        'levels': h.levels,
    }
