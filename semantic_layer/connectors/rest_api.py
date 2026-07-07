"""Generic REST API connector — infers schema from JSON responses."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Set

import requests

from semantic_layer.connectors.base import BaseConnector
from semantic_layer.models import (
    ColumnMetadata,
    SourceMetadata,
    SourceType,
    TableMetadata,
    TableProfile,
    ColumnProfile,
    ColumnSemantic,
)
from semantic_layer.profiling.semantics import infer_column_semantic
from semantic_layer.utils import retry, to_snake_case

logger = logging.getLogger('semantic_layer.connectors.rest_api')


class RestApiConnector(BaseConnector):
    source_type = SourceType.REST_API

    def connect(self, **kwargs: Any) -> None:
        self._session = requests.Session()
        headers = {}
        if self.config.get('api_key'):
            header_name = self.config.get('auth_header', 'Authorization')
            prefix = self.config.get('auth_prefix', 'Bearer')
            headers[header_name] = f'{prefix} {self.config["api_key"]}'.strip()
        if self.config.get('headers_json'):
            headers.update(json.loads(self.config['headers_json']))
        self._session.headers.update(headers)
        self._connected = True

    def disconnect(self) -> None:
        if hasattr(self, '_session'):
            self._session.close()
        self._connected = False

    @retry(attempts=3, delay=1.0)
    def _fetch_json(self, endpoint: str) -> Any:
        base = self.config.get('base_url', '').rstrip('/')
        url = f'{base}{endpoint}'
        resp = self._session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def discover_metadata(self, max_tables: int = 200) -> SourceMetadata:
        endpoints_raw = self.config.get('endpoints', '[]')
        try:
            endpoints = json.loads(endpoints_raw)
        except json.JSONDecodeError:
            endpoints = [e.strip() for e in endpoints_raw.split(',') if e.strip()]

        tables: List[TableMetadata] = []
        for ep in endpoints[:max_tables]:
            path = ep if isinstance(ep, str) else ep.get('path', '')
            name = ep.get('name', to_snake_case(path.strip('/').replace('/', '_'))) if isinstance(ep, dict) else to_snake_case(path.strip('/').replace('/', '_'))
            try:
                data = self._fetch_json(path)
                columns = self._infer_columns_from_json(data)
                tables.append(TableMetadata(
                    name=name,
                    comment=f'REST endpoint: {path}',
                    columns=columns,
                ))
            except Exception as exc:
                logger.warning('REST endpoint %s failed: %s', path, exc)

        return SourceMetadata(
            source_type=self.source_type,
            source_name=self.name,
            tables=tables,
        )

    def _infer_columns_from_json(self, data: Any, prefix: str = '') -> List[ColumnMetadata]:
        """Infer column schema from JSON object or array of objects."""
        if isinstance(data, list) and data:
            sample = data[0]
            if isinstance(sample, dict):
                return self._columns_from_dict(sample)
            return [ColumnMetadata(name='value', data_type=type(sample).__name__)]
        if isinstance(data, dict):
            items = data.get('data') or data.get('results') or data.get('items')
            if isinstance(items, list) and items and isinstance(items[0], dict):
                return self._columns_from_dict(items[0])
            return self._columns_from_dict(data)
        return []

    def _columns_from_dict(self, obj: Dict[str, Any]) -> List[ColumnMetadata]:
        cols: List[ColumnMetadata] = []
        for i, (key, val) in enumerate(obj.items()):
            dtype = 'object'
            if isinstance(val, bool):
                dtype = 'boolean'
            elif isinstance(val, int):
                dtype = 'integer'
            elif isinstance(val, float):
                dtype = 'float'
            elif isinstance(val, str):
                dtype = 'string'
            elif isinstance(val, list):
                dtype = 'array'
            cols.append(ColumnMetadata(name=key, data_type=dtype, ordinal_position=i + 1))
        return cols

    def profile_table(self, table: TableMetadata, sample_size: int = 1000) -> TableProfile:
        endpoints_raw = self.config.get('endpoints', '[]')
        endpoints = json.loads(endpoints_raw) if endpoints_raw.startswith('[') else []
        path = ''
        for ep in endpoints:
            ep_name = ep.get('name', '') if isinstance(ep, dict) else to_snake_case(ep.strip('/').replace('/', '_'))
            if ep_name == table.name:
                path = ep.get('path', ep) if isinstance(ep, dict) else ep
                break

        profiles: List[ColumnProfile] = []
        if path:
            try:
                data = self._fetch_json(path)
                records = self._extract_records(data)[:sample_size]
                for col in table.columns:
                    values = [str(r.get(col.name, '')) for r in records if isinstance(r, dict)]
                    distinct = len(set(values))
                    null_pct = (sum(1 for v in values if not v) / len(values) * 100) if values else 0
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
                logger.warning('REST profiling failed for %s: %s', table.name, exc)

        return TableProfile(table_name=table.name, columns=profiles)

    def _extract_records(self, data: Any) -> List[Dict]:
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            for key in ('data', 'results', 'items', 'contacts', 'opportunities'):
                if isinstance(data.get(key), list):
                    return [r for r in data[key] if isinstance(r, dict)]
            return [data]
        return []
