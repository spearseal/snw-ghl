"""Snowflake connector for semantic layer."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from semantic_layer.connectors.sql_base import SQLConnector
from semantic_layer.models import (
    ColumnMetadata,
    ConstraintMetadata,
    SourceType,
    TableMetadata,
)
from semantic_layer.utils import retry

logger = logging.getLogger('semantic_layer.connectors.snowflake')


class SnowflakeConnector(SQLConnector):
    source_type = SourceType.SNOWFLAKE

    def _get_connection(self, passcode: Optional[str] = None) -> Any:
        from snowflake_auth import snowflake_connect
        return snowflake_connect(self.config, passcode=passcode)

    def connect(self, **kwargs: Any) -> None:
        import snowflake.connector
        self.connection = self._get_connection(passcode=kwargs.get('passcode'))
        self.cursor = self.connection.cursor(snowflake.connector.DictCursor)
        self._connected = True

    def _discover_tables(self, database: str, schema: str, max_tables: int) -> List[TableMetadata]:
        db = database.upper()
        sch = schema.upper()
        rows = self._execute(
            """
            SELECT table_name, row_count, comment, table_type
            FROM information_schema.tables
            WHERE table_catalog = %s AND table_schema = %s
              AND table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY table_name
            LIMIT %s
            """,
            (db, sch, max_tables),
        )
        col_rows = self._execute(
            """
            SELECT table_name, column_name, data_type, is_nullable, comment, ordinal_position
            FROM information_schema.columns
            WHERE table_catalog = %s AND table_schema = %s
            ORDER BY table_name, ordinal_position
            """,
            (db, sch),
        )
        return self._build_tables(rows, col_rows, base_only=True)

    def _discover_views(self, database: str, schema: str, max_tables: int) -> List[TableMetadata]:
        db = database.upper()
        sch = schema.upper()
        rows = self._execute(
            """
            SELECT table_name, row_count, comment
            FROM information_schema.tables
            WHERE table_catalog = %s AND table_schema = %s AND table_type = 'VIEW'
            ORDER BY table_name LIMIT %s
            """,
            (db, sch, max_tables),
        )
        col_rows = self._execute(
            """
            SELECT table_name, column_name, data_type, is_nullable, comment, ordinal_position
            FROM information_schema.columns
            WHERE table_catalog = %s AND table_schema = %s
            ORDER BY table_name, ordinal_position
            """,
            (db, sch),
        )
        view_names = {r.get('TABLE_NAME') or r.get('table_name') for r in rows}
        tables = self._build_tables(rows, col_rows, base_only=False)
        return [t for t in tables if t.name in view_names]

    def _build_tables(
        self,
        table_rows: List[Dict],
        col_rows: List[Dict],
        base_only: bool,
    ) -> List[TableMetadata]:
        cols_by_table: Dict[str, List[ColumnMetadata]] = {}
        for row in col_rows:
            tname = row.get('TABLE_NAME') or row.get('table_name', '')
            cols_by_table.setdefault(tname, []).append(ColumnMetadata(
                name=row.get('COLUMN_NAME') or row.get('column_name', ''),
                data_type=row.get('DATA_TYPE') or row.get('data_type', ''),
                nullable=(row.get('IS_NULLABLE') or row.get('is_nullable', 'YES')) == 'YES',
                comment=row.get('COMMENT') or row.get('comment') or '',
                ordinal_position=int(row.get('ORDINAL_POSITION') or row.get('ordinal_position') or 0),
            ))

        tables: List[TableMetadata] = []
        for row in table_rows:
            ttype = row.get('TABLE_TYPE') or row.get('table_type', 'BASE TABLE')
            if base_only and ttype == 'VIEW':
                continue
            name = row.get('TABLE_NAME') or row.get('table_name', '')
            tables.append(TableMetadata(
                name=name,
                database_name=self.config.get('database', ''),
                schema_name=self.config.get('schema', ''),
                table_type='VIEW' if ttype == 'VIEW' else 'BASE TABLE',
                row_count=row.get('ROW_COUNT') or row.get('row_count'),
                comment=row.get('COMMENT') or row.get('comment') or '',
                columns=cols_by_table.get(name, []),
            ))
        return tables

    def _enrich_constraints(self, tables, database, schema) -> None:
        db = database.upper()
        sch = schema.upper()
        try:
            pk_rows = self._execute(
                """
                SELECT tc.table_name, kcu.column_name, tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.table_catalog = %s AND tc.table_schema = %s
                  AND tc.constraint_type = 'PRIMARY KEY'
                """,
                (db, sch),
            )
            fk_rows = self._execute(
                """
                SELECT
                  tc.table_name, kcu.column_name, tc.constraint_name,
                  ccu.table_name AS referenced_table,
                  ccu.column_name AS referenced_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                WHERE tc.table_catalog = %s AND tc.table_schema = %s
                  AND tc.constraint_type = 'FOREIGN KEY'
                """,
                (db, sch),
            )
        except Exception as exc:
            logger.warning('Snowflake constraint discovery failed: %s', exc)
            return

        table_map = {t.name: t for t in tables}
        for row in pk_rows:
            tname = row.get('TABLE_NAME') or row.get('table_name', '')
            cname = row.get('COLUMN_NAME') or row.get('column_name', '')
            if tname in table_map:
                for col in table_map[tname].columns:
                    if col.name == cname:
                        col.is_primary_key = True
                table_map[tname].constraints.append(ConstraintMetadata(
                    name=row.get('CONSTRAINT_NAME') or row.get('constraint_name', ''),
                    constraint_type='PRIMARY KEY',
                    columns=[cname],
                ))

        for row in fk_rows:
            tname = row.get('TABLE_NAME') or row.get('table_name', '')
            cname = row.get('COLUMN_NAME') or row.get('column_name', '')
            ref_t = row.get('REFERENCED_TABLE') or row.get('referenced_table', '')
            ref_c = row.get('REFERENCED_COLUMN') or row.get('referenced_column', '')
            if tname in table_map:
                for col in table_map[tname].columns:
                    if col.name == cname:
                        col.is_foreign_key = True
                table_map[tname].constraints.append(ConstraintMetadata(
                    name=row.get('CONSTRAINT_NAME') or row.get('constraint_name', ''),
                    constraint_type='FOREIGN KEY',
                    columns=[cname],
                    referenced_table=ref_t,
                    referenced_columns=[ref_c],
                ))
