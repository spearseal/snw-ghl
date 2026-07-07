"""JSON metadata document generator."""
from __future__ import annotations

from typing import Any, Dict, List

from semantic_layer.models import (
    InferredRelationship,
    SemanticMetadataDocument,
    SemanticModel,
    SourceMetadata,
    TableProfile,
)


def generate_json_metadata(
    model: SemanticModel,
    sources: List[SourceMetadata],
    profiles: List[TableProfile],
    relationships: List[InferredRelationship],
) -> SemanticMetadataDocument:
    """Generate complete JSON metadata for deployment."""
    source_doc: Dict[str, Any] = {
        'model_name': model.name,
        'model_version': model.version,
        'sources': [
            {
                'name': s.source_name,
                'type': s.source_type.value,
                'database': s.database,
                'schema': s.schema_name,
                'table_count': len(s.tables),
                'view_count': len(s.views),
            }
            for s in sources
        ],
    }

    tables: List[Dict[str, Any]] = []
    columns: List[Dict[str, Any]] = []
    for src in sources:
        for table in src.tables + src.views:
            tables.append({
                'source': src.source_name,
                'name': table.name,
                'schema': table.schema_name,
                'database': table.database_name,
                'type': table.table_type,
                'row_count': table.row_count,
                'comment': table.comment,
                'column_count': len(table.columns),
            })
            for col in table.columns:
                columns.append({
                    'source': src.source_name,
                    'table': table.name,
                    'name': col.name,
                    'data_type': col.data_type,
                    'nullable': col.nullable,
                    'is_primary_key': col.is_primary_key,
                    'is_foreign_key': col.is_foreign_key,
                    'comment': col.comment,
                })

    profile_lookup = {}
    for p in profiles:
        for c in p.columns:
            profile_lookup[(p.table_name, c.column_name)] = c

    for col_doc in columns:
        key = (col_doc['table'], col_doc['name'])
        if key in profile_lookup:
            prof = profile_lookup[key]
            col_doc['profile'] = {
                'null_pct': prof.null_pct,
                'distinct_count': prof.distinct_count,
                'min_value': prof.min_value,
                'max_value': prof.max_value,
                'sample_values': prof.sample_values,
                'cardinality': prof.cardinality,
                'inferred_semantic': prof.inferred_semantic.value,
                'confidence': prof.confidence,
            }

    rels = [
        {
            'from_table': r.from_table,
            'from_column': r.from_column,
            'to_table': r.to_table,
            'to_column': r.to_column,
            'relationship_type': r.relationship_type.value,
            'confidence': r.confidence,
            'inference_method': r.inference_method,
        }
        for r in relationships
    ]

    lineage = _build_lineage(model)

    return SemanticMetadataDocument(
        source=source_doc,
        tables=tables,
        columns=columns,
        relationships=rels,
        entities=[e.model_dump() for e in model.entities],
        dimensions=[d.model_dump() for d in model.dimensions],
        facts=[f.model_dump() for f in model.facts],
        measures=[m.model_dump() for m in model.measures],
        lineage=lineage,
    )


def _build_lineage(model: SemanticModel) -> List[Dict[str, Any]]:
    lineage: List[Dict[str, Any]] = []

    for entity in model.entities:
        lineage.append({
            'semantic_object': entity.name,
            'object_type': 'entity',
            'source_table': entity.source_table,
            'source_column': '',
        })

    for dim in model.dimensions:
        lineage.append({
            'semantic_object': dim.name,
            'object_type': 'dimension',
            'source_table': dim.source_table,
            'source_column': dim.source_column,
        })

    for measure in model.measures:
        lineage.append({
            'semantic_object': measure.name,
            'object_type': 'measure',
            'source_table': measure.source_table,
            'source_column': measure.source_column,
        })

    return lineage
