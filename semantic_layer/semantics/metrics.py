"""Reusable business metrics builder."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from semantic_layer.models import (
    BusinessEntity,
    ColumnProfile,
    ColumnSemantic,
    EntityType,
    Fact,
    Measure,
    SourceMetadata,
    TableProfile,
)
from semantic_layer.utils import to_business_name, to_snake_case

logger = logging.getLogger('semantic_layer.semantics.metrics')

AGGREGATION_MAP = {
    ColumnSemantic.CURRENCY: 'sum',
    ColumnSemantic.MEASURE: 'sum',
    ColumnSemantic.ID: 'count_distinct',
    ColumnSemantic.FOREIGN_KEY: 'count_distinct',
}


def build_facts_and_measures(
    entities: List[BusinessEntity],
    sources: List[SourceMetadata],
    profiles: List[TableProfile],
) -> tuple[List[Fact], List[Measure]]:
    """Build fact tables and reusable measures."""
    profile_map: Dict[str, Dict[str, ColumnProfile]] = {}
    for p in profiles:
        profile_map[p.table_name] = {c.column_name: c for c in p.columns}

    table_map: Dict[str, Any] = {}
    for src in sources:
        for table in src.tables:
            table_map[table.name] = table

    facts: List[Fact] = []
    measures: List[Measure] = []
    seen_measures: Set[str] = set()

    for entity in entities:
        if entity.entity_type != EntityType.FACT:
            continue

        table = table_map.get(entity.source_table)
        if not table:
            continue

        col_profiles = profile_map.get(entity.source_table, {})
        dim_names: List[str] = []
        measure_names: List[str] = []

        for col in table.columns:
            profile = col_profiles.get(col.name)
            semantic = profile.inferred_semantic if profile else ColumnSemantic.UNKNOWN

            if semantic in (ColumnSemantic.MEASURE, ColumnSemantic.CURRENCY):
                m_name = f'{to_snake_case(entity.name)}__{to_snake_case(col.name)}'
                if m_name not in seen_measures:
                    seen_measures.add(m_name)
                    agg = AGGREGATION_MAP.get(semantic, 'sum')
                    measures.append(Measure(
                        name=m_name,
                        business_name=f'Total {to_business_name(col.name)}',
                        description=f'Sum of {to_business_name(col.name)} from {entity.business_name}',
                        expression=f'SUM({col.name})',
                        aggregation=agg,
                        source_table=entity.source_table,
                        source_column=col.name,
                        format='currency' if semantic == ColumnSemantic.CURRENCY else 'number',
                    ))
                    measure_names.append(m_name)
            elif semantic in (
                ColumnSemantic.FOREIGN_KEY, ColumnSemantic.EMAIL, ColumnSemantic.STATUS,
                ColumnSemantic.DATE, ColumnSemantic.DATETIME, ColumnSemantic.CATEGORY,
            ):
                dim_names.append(f'{to_snake_case(entity.source_table)}__{to_snake_case(col.name)}')

        # Default count measure per fact
        count_name = f'{to_snake_case(entity.name)}__count'
        if count_name not in seen_measures:
            seen_measures.add(count_name)
            measures.append(Measure(
                name=count_name,
                business_name=f'{entity.business_name} Count',
                description=f'Count of records in {entity.business_name}',
                expression='COUNT(*)',
                aggregation='count',
                source_table=entity.source_table,
            ))
            measure_names.append(count_name)

        facts.append(Fact(
            name=to_snake_case(entity.name),
            business_name=entity.business_name,
            description=entity.description,
            source_table=entity.source_table,
            grain=entity.primary_key or ['id'],
            dimensions=dim_names,
            measures=measure_names,
        ))

    return facts, measures
