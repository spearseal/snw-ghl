"""PostgreSQL connector."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from semantic_layer.connectors.sql_base import SQLConnector
from semantic_layer.models import ColumnMetadata, ConstraintMetadata, SourceType, TableMetadata

logger = logging.getLogger('semantic_layer.connectors.postgresql')


class PostgreSQLConnector(SQLConnector):
    source_type = SourceType.POSTGRESQL

    def _get_connection(self) -> Any:
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError as exc:
            raise ImportError(
                'psycopg2 is required for PostgreSQL. Install with: pip install psycopg2-binary'
            ) from exc

        return psycopg2.connect(
            host=self.config.get('host', 'localhost'),
            port=int(self.config.get('port', '5432')),
            database=self.config.get('database', 'postgres'),
            user=self.config.get('user', ''),
            password=self.config.get('password', ''),
            connect_timeout=30,
        )

    def connect(self, **kwargs: Any) -> None:
        import psycopg2.extras
        self.connection = self._get_connection()
        self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        self._connected = True

    def _discover_tables(self, database: str, schema: str, max_tables: int) -> List[TableMetadata]:
        schema = schema or 'public'
        rows = self._execute(
            """
            SELECT t.table_name, c.reltuples::bigint AS row_count, obj_description(c.oid) AS comment
            FROM information_schema.tables t
            JOIN pg_class c ON c.relname = t.table_name
            JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = t.table_schema
            WHERE t.table_schema = %s AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name LIMIT %s
            """,
            (schema, max_tables),
        )
        col_rows = self._execute(
            """
            SELECT table_name, column_name, data_type, is_nullable,
                   col_description((quote_ident(table_schema)||'.'||quote_ident(table_name))::regclass::oid,
                   ordinal_position) AS comment,
                   ordinal_position
            FROM information_schema.columns
            WHERE table_schema = %s ORDER BY table_name, ordinal_position
            """,
            (schema,),
        )
        return self._build_pg_tables(rows, col_rows, schema, 'BASE TABLE')

    def _discover_views(self, database: str, schema: str, max_tables: int) -> List[TableMetadata]:
        schema = schema or 'public'
        rows = self._execute(
            """
            SELECT table_name, NULL::bigint AS row_count, NULL AS comment
            FROM information_schema.views WHERE table_schema = %s
            ORDER BY table_name LIMIT %s
            """,
            (schema, max_tables),
        )
        col_rows = self._execute(
            """
            SELECT table_name, column_name, data_type, is_nullable, '' AS comment, ordinal_position
            FROM information_schema.columns
            WHERE table_schema = %s ORDER BY table_name, ordinal_position
            """,
            (schema,),
        )
        return self._build_pg_tables(rows, col_rows, schema, 'VIEW')

    def _build_pg_tables(self, table_rows, col_rows, schema, table_type) -> List[TableMetadata]:
        cols_by: Dict[str, List[ColumnMetadata]] = {}
        for row in col_rows:
            tname = row['table_name']
            cols_by.setdefault(tname, []).append(ColumnMetadata(
                name=row['column_name'],
                data_type=row['data_type'],
                nullable=row['is_nullable'] == 'YES',
                comment=str(row.get('comment') or ''),
                ordinal_position=int(row.get('ordinal_position') or 0),
            ))
        return [
            TableMetadata(
                name=row['table_name'],
                schema_name=schema,
                database_name=self.config.get('database', ''),
                table_type=table_type,
                row_count=row.get('row_count'),
                comment=str(row.get('comment') or ''),
                columns=cols_by.get(row['table_name'], []),
            )
            for row in table_rows
        ]

    def _enrich_constraints(self, tables, database, schema) -> None:
        schema = schema or 'public'
        try:
            pk_rows = self._execute(
                """
                SELECT tc.table_name, kcu.column_name, tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_schema = %s AND tc.constraint_type = 'PRIMARY KEY'
                """,
                (schema,),
            )
            fk_rows = self._execute(
                """
                SELECT tc.table_name, kcu.column_name, ccu.table_name AS referenced_table,
                       ccu.column_name AS referenced_column, tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
                WHERE tc.table_schema = %s AND tc.constraint_type = 'FOREIGN KEY'
                """,
                (schema,),
            )
        except Exception as exc:
            logger.warning('PostgreSQL constraint discovery failed: %s', exc)
            return

        table_map = {t.name: t for t in tables}
        for row in pk_rows:
            tname, cname = row['table_name'], row['column_name']
            if tname in table_map:
                for col in table_map[tname].columns:
                    if col.name == cname:
                        col.is_primary_key = True
        for row in fk_rows:
            tname, cname = row['table_name'], row['column_name']
            if tname in table_map:
                for col in table_map[tname].columns:
                    if col.name == cname:
                        col.is_foreign_key = True
