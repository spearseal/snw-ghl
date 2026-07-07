"""Semantic model assembly."""
from __future__ import annotations

import logging
from typing import List

from semantic_layer.models import (
    Hierarchy,
    InferredRelationship,
    SemanticModel,
    SemanticRelationship,
    SourceMetadata,
    TableProfile,
)
from semantic_layer.semantics.dimensions import build_dimensions
from semantic_layer.semantics.entity_detector import detect_entities
from semantic_layer.semantics.metrics import build_facts_and_measures
from semantic_layer.utils import to_business_name, to_snake_case

logger = logging.getLogger('semantic_layer.semantics.model_builder')


def build_semantic_model(
    name: str,
    description: str,
    sources: List[SourceMetadata],
    profiles: List[TableProfile],
    relationships: List[InferredRelationship],
) -> SemanticModel:
    """Assemble the full semantic model from discovered metadata."""
    entities = detect_entities(sources, profiles)
    dimensions = build_dimensions(sources, profiles, entities)
    facts, measures = build_facts_and_measures(entities, sources, profiles)
    semantic_rels = _build_semantic_relationships(relationships, entities)
    hierarchies = _build_hierarchies(dimensions)

    return SemanticModel(
        name=name,
        description=description,
        sources=[s.source_name for s in sources],
        entities=entities,
        dimensions=dimensions,
        facts=facts,
        measures=measures,
        hierarchies=hierarchies,
        relationships=semantic_rels,
    )


def _build_semantic_relationships(
    relationships: List[InferredRelationship],
    entities: List,
) -> List[SemanticRelationship]:
    entity_by_table = {e.source_table: e.name for e in entities}
    result: List[SemanticRelationship] = []

    for rel in relationships:
        from_entity = entity_by_table.get(rel.from_table, to_snake_case(rel.from_table))
        to_entity = entity_by_table.get(rel.to_table, to_snake_case(rel.to_table))
        result.append(SemanticRelationship(
            name=f'{from_entity}_to_{to_entity}',
            from_entity=from_entity,
            to_entity=to_entity,
            from_column=rel.from_column,
            to_column=rel.to_column,
            relationship_type=rel.relationship_type,
            confidence=rel.confidence,
        ))

    return result


def _build_hierarchies(dimensions: List) -> List[Hierarchy]:
    """Build date and geographic hierarchies from dimensions."""
    hierarchies: List[Hierarchy] = []
    date_dims = [d for d in dimensions if d.semantic.value in ('date', 'datetime')]
    if date_dims:
        hierarchies.append(Hierarchy(
            name='date_hierarchy',
            dimension='date',
            levels=['year', 'quarter', 'month', 'day'],
        ))

    geo_patterns = ['country', 'state', 'city', 'zip', 'postal']
    geo_dims = [d for d in dimensions if any(p in d.source_column.lower() for p in geo_patterns)]
    if len(geo_dims) >= 2:
        hierarchies.append(Hierarchy(
            name='geography_hierarchy',
            dimension='geography',
            levels=[d.source_column for d in geo_dims[:4]],
        ))

    return hierarchies
