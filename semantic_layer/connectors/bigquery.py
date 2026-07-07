"""BigQuery connector."""
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
)
from semantic_layer.profiling.profiler import profile_table_columns
from semantic_layer.utils import retry

logger = logging.getLogger('semantic_layer.connectors.bigquery')


class BigQueryConnector(BaseConnector):
    source_type = SourceType.BIGQUERY

    def __init__(self, name: str, config: Dict[str, str]):
        super().__init__(name, config)
        self._client: Any = None

    def _get_client(self) -> Any:
        try:
            from google.cloud import bigquery
        except ImportError as exc:
            raise ImportError(
                'google-cloud-bigquery is required. Install with: pip install google-cloud-bigquery'
            ) from exc

        project = self.config.get('project_id') or self.config.get('project', '')
        if self.config.get('credentials_path'):
            return bigquery.Client.from_service_account_json(
                self.config['credentials_path'], project=project
            )
        return bigquery.Client(project=project)

    def connect(self, **kwargs: Any) -> None:
        self._client = self._get_client()
        self._connected = True

    def disconnect(self) -> None:
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None
        self._connected = False

    @retry(attempts=3, delay=1.0)
    def discover_metadata(self, max_tables: int = 200) -> SourceMetadata:
        project = self.config.get('project_id') or self.config.get('project', '')
        dataset = self.config.get('dataset') or self.config.get('schema', '')
        if not dataset:
            raise ValueError('BigQuery dataset is required')

        tables: List[TableMetadata] = []
        views: List[TableMetadata] = []

        for table_ref in list(self._client.list_tables(f'{project}.{dataset}'))[:max_tables]:
            table = self._client.get_table(table_ref)
            cols = [
                ColumnMetadata(
                    name=f.name,
                    data_type=f.field_type,
                    nullable=f.is_nullable if hasattr(f, 'is_nullable') else f.mode != 'REQUIRED',
                    comment=f.description or '',
                )
                for f in table.schema
            ]
            meta = TableMetadata(
                name=table.table_id,
                database_name=project,
                schema_name=dataset,
                table_type='VIEW' if table.table_type == 'VIEW' else 'BASE TABLE',
                row_count=table.num_rows,
                comment=table.description or '',
                columns=cols,
            )
            if table.table_type == 'VIEW':
                views.append(meta)
            else:
                tables.append(meta)

        return SourceMetadata(
            source_type=self.source_type,
            source_name=self.name,
            database=project,
            schema_name=dataset,
            tables=tables,
            views=views,
        )

    def profile_table(self, table: TableMetadata, sample_size: int = 1000) -> TableProfile:
        project = self.config.get('project_id') or self.config.get('project', '')
        dataset = self.config.get('dataset') or self.config.get('schema', '')
        qualified = f'`{project}.{dataset}.{table.name}`'

        def execute_fn(sql: str) -> List[Dict[str, Any]]:
            job = self._client.query(sql)
            return [dict(row) for row in job.result()]

        return profile_table_columns(
            execute_fn=execute_fn,
            table=table,
            qualified_name=qualified,
            sample_size=sample_size,
            dialect='bigquery',
        )
