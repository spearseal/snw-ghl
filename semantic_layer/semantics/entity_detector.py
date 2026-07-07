"""Business entity detection from tables and profiles."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

from semantic_layer.models import (
    BusinessEntity,
    ColumnProfile,
    ColumnSemantic,
    EntityType,
    SourceMetadata,
    TableMetadata,
    TableProfile,
)
from semantic_layer.utils import is_lookup_table, singularize, to_business_name, to_snake_case

logger = logging.getLogger('semantic_layer.semantics.entities')

FACT_HINTS = {'fact', 'transaction', 'event', 'order', 'payment', 'appointment', 'visit', 'sale'}
DIM_HINTS = {'dim', 'dimension', 'lookup', 'ref_', 'code', 'type', 'status'}
BRIDGE_HINTS = {'bridge', 'xref', 'mapping', 'junction', 'link'}


def detect_entities(
    sources: List[SourceMetadata],
    profiles: List[TableProfile],
) -> List[BusinessEntity]:
    """Identify business entities from discovered tables."""
    profile_map: Dict[str, TableProfile] = {p.table_name: p for p in profiles}
    entities: List[BusinessEntity] = []
    seen: Set[str] = set()

    for src in sources:
        for table in src.tables + src.views:
            if table.name in seen:
                continue
            seen.add(table.name)

            profile = profile_map.get(table.name)
            entity_type = _classify_entity(table, profile)
            pk = _detect_primary_key(table, profile)
            entity_name = to_snake_case(singularize(table.name))

            synonyms = _build_synonyms(table.name, entity_name)
            entities.append(BusinessEntity(
                name=entity_name,
                business_name=to_business_name(singularize(table.name)),
                description=table.comment or f'{to_business_name(table.name)} entity from {src.source_name}',
                source_table=table.name,
                entity_type=entity_type,
                primary_key=pk,
                synonyms=synonyms,
            ))

    return entities


def _classify_entity(table: TableMetadata, profile: Optional[TableProfile]) -> EntityType:
    name = table.name.lower()

    if any(h in name for h in BRIDGE_HINTS):
        return EntityType.BRIDGE
    if is_lookup_table(table.name, len(table.columns), table.row_count):
        return EntityType.LOOKUP
    if any(h in name for h in DIM_HINTS):
        return EntityType.DIMENSION

    measure_cols = 0
    fk_cols = 0
    if profile:
        for col in profile.columns:
            if col.inferred_semantic == ColumnSemantic.MEASURE:
                measure_cols += 1
            if col.inferred_semantic == ColumnSemantic.FOREIGN_KEY:
                fk_cols += 1
    else:
        for col in table.columns:
            if col.is_foreign_key:
                fk_cols += 1

    if any(h in name for h in FACT_HINTS):
        return EntityType.FACT
    if measure_cols >= 2 or (fk_cols >= 2 and measure_cols >= 1):
        return EntityType.FACT
    if fk_cols >= 1 and measure_cols == 0:
        return EntityType.DIMENSION

    return EntityType.DIMENSION


def _detect_primary_key(table: TableMetadata, profile: Optional[TableProfile]) -> List[str]:
    pk = [c.name for c in table.columns if c.is_primary_key]
    if pk:
        return pk

    id_cols = [c.name for c in table.columns if c.name.lower() == 'id']
    if id_cols:
        return id_cols

    if profile:
        unique_cols = [c.column_name for c in profile.columns if c.cardinality == 'unique']
        if len(unique_cols) == 1:
            return unique_cols

    return []


def _build_synonyms(table_name: str, entity_name: str) -> List[str]:
    synonyms = {table_name, entity_name}
    base = table_name.lower()
    if base.startswith('ghl_'):
        synonyms.add(base[4:])
    synonyms.add(singularize(base))
    return sorted(synonyms - {entity_name})
