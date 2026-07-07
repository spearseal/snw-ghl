"""
SQL-based connector base for INFORMATION_SCHEMA sources.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from semantic_layer.connectors.base import BaseConnector
from semantic_layer.models import (
    ColumnMetadata,
    ConstraintMetadata,
    SourceMetadata,
    SourceType,
    TableMetadata,
    TableProfile,
)
from semantic_layer.profiling.profiler import profile_table_columns
from semantic_layer.utils import retry, safe_ident

logger = logging.getLogger('semantic_layer.connectors.sql')


class SQLConnector(BaseConnector):
    """Base class for databases exposing INFORMATION_SCHEMA."""

    source_type: SourceType = SourceType.POSTGRESQL

    def __init__(self, name: str, config: Dict[str, str]):
        super().__init__(name, config)
        self.connection: Any = None
        self.cursor: Any = None

    @abstractmethod
    def _get_connection(self) -> Any:
        ...

    def connect(self, **kwargs: Any) -> None:
        self.connection = self._get_connection()
        self.cursor = self.connection.cursor()
        self._connected = True

    def disconnect(self) -> None:
        if self.cursor:
            try:
                self.cursor.close()
            except Exception:
                pass
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
        self.cursor = None
        self.connection = None
        self._connected = False

    @retry(attempts=3, delay=1.0)
    def _execute(self, sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        self.cursor.execute(sql, params or ())
        if not self.cursor.description:
            return []
        cols = [d[0] for d in self.cursor.description]
        return [dict(zip(cols, row)) for row in self.cursor.fetchall()]

    def _database_schema(self) -> Tuple[str, str]:
        database = (self.config.get('database') or '').strip()
        schema = (self.config.get('schema') or 'public').strip()
        return database, schema

    def discover_metadata(self, max_tables: int = 200) -> SourceMetadata:
        database, schema = self._database_schema()
        tables = self._discover_tables(database, schema, max_tables)
        views = self._discover_views(database, schema, max_tables)
        self._enrich_constraints(tables + views, database, schema)
        return SourceMetadata(
            source_type=self.source_type,
            source_name=self.name,
            database=database,
            schema_name=schema,
            tables=tables,
            views=views,
        )

    def _discover_tables(self, database: str, schema: str, max_tables: int) -> List[TableMetadata]:
        raise NotImplementedError

    def _discover_views(self, database: str, schema: str, max_tables: int) -> List[TableMetadata]:
        return []

    def _enrich_constraints(
        self,
        tables: List[TableMetadata],
        database: str,
        schema: str,
    ) -> None:
        raise NotImplementedError

    def profile_table(self, table: TableMetadata, sample_size: int = 1000) -> TableProfile:
        qualified = self._qualified_name(table)
        return profile_table_columns(
            execute_fn=self._execute_scalar_and_fetch,
            table=table,
            qualified_name=qualified,
            sample_size=sample_size,
        )

    def _qualified_name(self, table: TableMetadata) -> str:
        database, schema = self._database_schema()
        parts = []
        if database:
            parts.append(safe_ident(database))
        if schema:
            parts.append(safe_ident(schema))
        parts.append(safe_ident(table.name))
        return '.'.join(parts)

    def _execute_scalar_and_fetch(self, sql: str) -> List[Dict[str, Any]]:
        return self._execute(sql)
