"""Conformed dimension builder."""
from __future__ import annotations

import logging
from typing import Dict, List, Set

from semantic_layer.models import (
    BusinessEntity,
    ColumnProfile,
    ColumnSemantic,
    Dimension,
    EntityType,
    SourceMetadata,
    TableProfile,
)
from semantic_layer.utils import to_business_name, to_snake_case

logger = logging.getLogger('semantic_layer.semantics.dimensions')

# Columns that should be conformed across entities
CONFORMED_PATTERNS = {
    'date': ['date', 'created', 'updated', 'modified', 'timestamp'],
    'customer': ['contact', 'customer', 'patient', 'client'],
    'location': ['location', 'site', 'branch', 'facility'],
    'status': ['status', 'state', 'stage'],
}

DIM_SEMANTICS = {
    ColumnSemantic.EMAIL, ColumnSemantic.PHONE, ColumnSemantic.NAME,
    ColumnSemantic.ADDRESS, ColumnSemantic.STATUS, ColumnSemantic.CATEGORY,
    ColumnSemantic.DATE, ColumnSemantic.DATETIME, ColumnSemantic.BOOLEAN,
}


def build_dimensions(
    sources: List[SourceMetadata],
    profiles: List[TableProfile],
    entities: List[BusinessEntity],
) -> List[Dimension]:
    """Build dimension definitions from entities and profiles."""
    profile_map: Dict[str, Dict[str, ColumnProfile]] = {}
    for p in profiles:
        profile_map[p.table_name] = {c.column_name: c for c in p.columns}

    entity_map = {e.source_table: e for e in entities}
    dimensions: List[Dimension] = []
    seen: Set[str] = set()

    for src in sources:
        for table in src.tables + src.views:
            entity = entity_map.get(table.name)
            col_profiles = profile_map.get(table.name, {})

            for col in table.columns:
                profile = col_profiles.get(col.name)
                semantic = profile.inferred_semantic if profile else ColumnSemantic.UNKNOWN

                if entity and entity.entity_type == EntityType.FACT:
                    if semantic not in DIM_SEMANTICS and not col.is_foreign_key:
                        if semantic != ColumnSemantic.FOREIGN_KEY:
                            continue

                dim_name = f'{to_snake_case(table.name)}__{to_snake_case(col.name)}'
                if dim_name in seen:
                    continue
                seen.add(dim_name)

                is_conformed = _is_conformed(col.name, semantic)
                dimensions.append(Dimension(
                    name=dim_name,
                    business_name=to_business_name(col.name),
                    description=col.comment or f'{to_business_name(col.name)} from {to_business_name(table.name)}',
                    source_table=table.name,
                    source_column=col.name,
                    data_type=col.data_type,
                    semantic=semantic,
                    is_conformed=is_conformed,
                    synonyms=_dim_synonyms(col.name, table.name),
                ))

    return dimensions


def _is_conformed(column_name: str, semantic: ColumnSemantic) -> bool:
    name = column_name.lower()
    for group, patterns in CONFORMED_PATTERNS.items():
        if any(p in name for p in patterns):
            return True
    return semantic in (ColumnSemantic.DATE, ColumnSemantic.DATETIME, ColumnSemantic.STATUS)


def _dim_synonyms(column_name: str, table_name: str) -> List[str]:
    syns = {column_name}
    if column_name.lower().endswith('id'):
        syns.add(column_name.lower().replace('_id', ''))
    return sorted(syns)
