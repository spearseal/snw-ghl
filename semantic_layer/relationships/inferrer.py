"""Automatic relationship discovery with confidence scoring."""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from semantic_layer.models import (
    InferredRelationship,
    RelationshipType,
    SourceMetadata,
    TableMetadata,
)
from semantic_layer.utils import is_id_column, is_lookup_table, singularize

logger = logging.getLogger('semantic_layer.relationships')


def infer_relationships(
    sources: List[SourceMetadata],
    min_confidence: float = 0.6,
) -> List[InferredRelationship]:
    """Infer PK/FK and lookup relationships across all discovered sources."""
    all_tables: Dict[str, TableMetadata] = {}
    table_source: Dict[str, str] = {}

    for src in sources:
        for table in src.tables + src.views:
            key = f'{src.source_name}.{table.name}'
            all_tables[key] = table
            table_source[key] = src.source_name

    relationships: List[InferredRelationship] = []
    seen: Set[Tuple[str, str, str, str]] = set()

    # 1. Explicit foreign keys from constraints
    for key, table in all_tables.items():
        for constraint in table.constraints:
            if constraint.constraint_type == 'FOREIGN KEY' and constraint.referenced_table:
                ref_key = _find_table_key(all_tables, constraint.referenced_table, key)
                if ref_key:
                    rel = InferredRelationship(
                        from_table=table.name,
                        from_column=constraint.columns[0] if constraint.columns else '',
                        to_table=all_tables[ref_key].name,
                        to_column=constraint.referenced_columns[0] if constraint.referenced_columns else 'id',
                        relationship_type=RelationshipType.ONE_TO_MANY,
                        confidence=1.0,
                        inference_method='catalog_foreign_key',
                    )
                    sig = (rel.from_table, rel.from_column, rel.to_table, rel.to_column)
                    if sig not in seen:
                        seen.add(sig)
                        relationships.append(rel)

        # PK-marked columns
        for col in table.columns:
            if col.is_foreign_key and col.is_primary_key:
                continue
            if col.is_foreign_key:
                ref = _infer_ref_from_fk_column(col.name, all_tables, table.name)
                if ref:
                    rel = InferredRelationship(
                        from_table=table.name,
                        from_column=col.name,
                        to_table=ref[0],
                        to_column=ref[1],
                        relationship_type=RelationshipType.ONE_TO_MANY,
                        confidence=0.95,
                        inference_method='catalog_foreign_key',
                    )
                    sig = (rel.from_table, rel.from_column, rel.to_table, rel.to_column)
                    if sig not in seen:
                        seen.add(sig)
                        relationships.append(rel)

    # 2. Naming convention: *_id columns
    for key, table in all_tables.items():
        for col in table.columns:
            if not is_id_column(col.name) or col.name.lower() == 'id':
                continue
            ref = _infer_ref_from_fk_column(col.name, all_tables, table.name)
            if ref:
                rel = InferredRelationship(
                    from_table=table.name,
                    from_column=col.name,
                    to_table=ref[0],
                    to_column=ref[1],
                    relationship_type=RelationshipType.ONE_TO_MANY,
                    confidence=0.75,
                    inference_method='naming_convention',
                )
                sig = (rel.from_table, rel.from_column, rel.to_table, rel.to_column)
                if sig not in seen:
                    seen.add(sig)
                    relationships.append(rel)

    # 3. Lookup table detection
    for key, table in all_tables.items():
        if is_lookup_table(table.name, len(table.columns), table.row_count):
            pk_cols = [c.name for c in table.columns if c.is_primary_key]
            if not pk_cols:
                pk_cols = [c.name for c in table.columns if c.name.lower() == 'id']
            if pk_cols:
                for other_key, other in all_tables.items():
                    if other.name == table.name:
                        continue
                    for col in other.columns:
                        if col.name.lower() in (
                            f'{table.name.lower()}_id',
                            f'{singularize(table.name).lower()}_id',
                            table.name.lower(),
                        ):
                            rel = InferredRelationship(
                                from_table=other.name,
                                from_column=col.name,
                                to_table=table.name,
                                to_column=pk_cols[0],
                                relationship_type=RelationshipType.LOOKUP,
                                confidence=0.7,
                                inference_method='lookup_detection',
                            )
                            sig = (rel.from_table, rel.from_column, rel.to_table, rel.to_column)
                            if sig not in seen:
                                seen.add(sig)
                                relationships.append(rel)

    return [r for r in relationships if r.confidence >= min_confidence]


def _find_table_key(all_tables: Dict[str, TableMetadata], ref_name: str, context_key: str) -> Optional[str]:
    for key, table in all_tables.items():
        if table.name.lower() == ref_name.lower():
            return key
    return None


def _infer_ref_from_fk_column(
    col_name: str,
    all_tables: Dict[str, TableMetadata],
    current_table: str,
) -> Optional[Tuple[str, str]]:
    """Infer referenced table and column from e.g. contact_id -> contacts.id."""
    base = col_name.lower()
    if base.endswith('_id'):
        base = base[:-3]
    elif base.endswith('id') and len(base) > 2:
        base = base[:-2]

    candidates = [
        base,
        singularize(base),
        base + 's',
        base + 'es',
        'ghl_' + base,
        'ghl_' + base + 's',
    ]

    for key, table in all_tables.items():
        if table.name.lower() == current_table.lower():
            continue
        if table.name.lower() in candidates or singularize(table.name.lower()) == base:
            pk = next((c.name for c in table.columns if c.is_primary_key), None)
            if not pk:
                pk = next((c.name for c in table.columns if c.name.lower() == 'id'), 'id')
            return table.name, pk

    return None
