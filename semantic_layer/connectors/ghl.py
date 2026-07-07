"""GoHighLevel connector — infers schema from API resources."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from semantic_layer.connectors.base import BaseConnector
from semantic_layer.models import (
    ColumnMetadata,
    SourceMetadata,
    SourceType,
    TableMetadata,
    TableProfile,
    ColumnProfile,
)
from semantic_layer.profiling.semantics import infer_column_semantic
from semantic_layer.utils import retry

logger = logging.getLogger('semantic_layer.connectors.ghl')

GHL_RESOURCES = [
    {'name': 'ghl_contacts', 'method': 'get_contacts', 'entity': 'contacts'},
    {'name': 'ghl_conversations', 'method': 'get_conversations', 'entity': 'conversations'},
    {'name': 'ghl_opportunities', 'method': 'get_opportunities', 'entity': 'opportunities'},
]


class GHLConnector(BaseConnector):
    source_type = SourceType.GHL

    def __init__(self, name: str, config: Dict[str, str]):
        super().__init__(name, config)
        self._client: Any = None

    def connect(self, **kwargs: Any) -> None:
        from ghl_client import GHLClient
        self._client = GHLClient(self.config)
        self._connected = True

    def disconnect(self) -> None:
        self._client = None
        self._connected = False

    @retry(attempts=3, delay=1.0)
    def discover_metadata(self, max_tables: int = 200) -> SourceMetadata:
        tables: List[TableMetadata] = []
        for resource in GHL_RESOURCES[:max_tables]:
            try:
                method = getattr(self._client, resource['method'])
                data, _ = method()
                records = data if isinstance(data, list) else []
                if not records:
                    tables.append(TableMetadata(
                        name=resource['name'],
                        comment=f'GHL {resource["entity"]} (no sample data)',
                        columns=self._default_ghl_columns(resource['entity']),
                    ))
                    continue
                columns = self._infer_columns(records[0])
                tables.append(TableMetadata(
                    name=resource['name'],
                    comment=f'GoHighLevel {resource["entity"]}',
                    row_count=len(records),
                    columns=columns,
                ))
            except Exception as exc:
                logger.warning('GHL resource %s discovery failed: %s', resource['name'], exc)
                tables.append(TableMetadata(
                    name=resource['name'],
                    comment=f'GHL {resource["entity"]} (discovery error)',
                    columns=self._default_ghl_columns(resource['entity']),
                ))

        return SourceMetadata(
            source_type=self.source_type,
            source_name=self.name,
            tables=tables,
        )

    def _default_ghl_columns(self, entity: str) -> List[ColumnMetadata]:
        defaults = {
            'contacts': ['id', 'firstName', 'lastName', 'email', 'phone', 'dateAdded', 'tags'],
            'conversations': ['id', 'contactId', 'body', 'type', 'dateAdded'],
            'opportunities': ['id', 'contactId', 'name', 'status', 'monetaryValue', 'pipelineId'],
        }
        return [
            ColumnMetadata(name=c, data_type='string', ordinal_position=i + 1)
            for i, c in enumerate(defaults.get(entity, ['id']))
        ]

    def _infer_columns(self, record: Dict[str, Any]) -> List[ColumnMetadata]:
        cols: List[ColumnMetadata] = []
        for i, (key, val) in enumerate(record.items()):
            dtype = 'string'
            if isinstance(val, bool):
                dtype = 'boolean'
            elif isinstance(val, (int, float)):
                dtype = 'number'
            elif isinstance(val, list):
                dtype = 'array'
            elif isinstance(val, dict):
                dtype = 'object'
            cols.append(ColumnMetadata(name=key, data_type=dtype, ordinal_position=i + 1))
        return cols

    def profile_table(self, table: TableMetadata, sample_size: int = 1000) -> TableProfile:
        resource = next((r for r in GHL_RESOURCES if r['name'] == table.name), None)
        profiles: List[ColumnProfile] = []
        if not resource:
            return TableProfile(table_name=table.name, columns=profiles)

        try:
            method = getattr(self._client, resource['method'])
            data, _ = method()
            records = (data if isinstance(data, list) else [])[:sample_size]
            for col in table.columns:
                values = []
                for r in records:
                    v = r.get(col.name)
                    if v is not None:
                        values.append(str(v)[:200])
                distinct = len(set(values))
                null_pct = (
                    (len(records) - len(values)) / len(records) * 100 if records else 0
                )
                semantic, conf = infer_column_semantic(col.name, col.data_type, values[:20])
                profiles.append(ColumnProfile(
                    column_name=col.name,
                    table_name=table.name,
                    null_pct=null_pct,
                    distinct_count=distinct,
                    sample_values=values[:5],
                    inferred_semantic=semantic,
                    confidence=conf,
                ))
        except Exception as exc:
            logger.warning('GHL profiling failed for %s: %s', table.name, exc)

        return TableProfile(
            table_name=table.name,
            row_count=table.row_count,
            columns=profiles,
        )
