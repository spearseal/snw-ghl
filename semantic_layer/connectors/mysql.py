"""MySQL connector."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from semantic_layer.connectors.sql_base import SQLConnector
from semantic_layer.models import ColumnMetadata, SourceType, TableMetadata

logger = logging.getLogger('semantic_layer.connectors.mysql')


class MySQLConnector(SQLConnector):
    source_type = SourceType.MYSQL

    def _get_connection(self) -> Any:
        try:
            import pymysql
            import pymysql.cursors
        except ImportError as exc:
            raise ImportError('pymysql is required for MySQL. Install with: pip install pymysql') from exc

        return pymysql.connect(
            host=self.config.get('host', 'localhost'),
            port=int(self.config.get('port', '3306')),
            database=self.config.get('database', ''),
            user=self.config.get('user', ''),
            password=self.config.get('password', ''),
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=30,
        )

    def _discover_tables(self, database: str, schema: str, max_tables: int) -> List[TableMetadata]:
        db = database or self.config.get('database', '')
        rows = self._execute(
            """
            SELECT TABLE_NAME AS table_name, TABLE_ROWS AS row_count, TABLE_COMMENT AS comment
            FROM information_schema.tables
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME LIMIT %s
            """,
            (db, max_tables),
        )
        col_rows = self._execute(
            """
            SELECT TABLE_NAME AS table_name, COLUMN_NAME AS column_name, DATA_TYPE AS data_type,
                   IS_NULLABLE AS is_nullable, COLUMN_COMMENT AS comment, ORDINAL_POSITION AS ordinal_position
            FROM information_schema.columns
            WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME, ORDINAL_POSITION
            """,
            (db,),
        )
        return self._build_mysql_tables(rows, col_rows, db)

    def _discover_views(self, database: str, schema: str, max_tables: int) -> List[TableMetadata]:
        db = database or self.config.get('database', '')
        rows = self._execute(
            """
            SELECT TABLE_NAME AS table_name, 0 AS row_count, '' AS comment
            FROM information_schema.views WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME LIMIT %s
            """,
            (db, max_tables),
        )
        col_rows = self._execute(
            """
            SELECT TABLE_NAME AS table_name, COLUMN_NAME AS column_name, DATA_TYPE AS data_type,
                   IS_NULLABLE AS is_nullable, COLUMN_COMMENT AS comment, ORDINAL_POSITION AS ordinal_position
            FROM information_schema.columns
            WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME, ORDINAL_POSITION
            """,
            (db,),
        )
        tables = self._build_mysql_tables(rows, col_rows, db)
        for t in tables:
            t.table_type = 'VIEW'
        return tables

    def _build_mysql_tables(self, table_rows, col_rows, db) -> List[TableMetadata]:
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
                database_name=db,
                row_count=row.get('row_count'),
                comment=str(row.get('comment') or ''),
                columns=cols_by.get(row['table_name'], []),
            )
            for row in table_rows
        ]

    def _enrich_constraints(self, tables, database, schema) -> None:
        db = database or self.config.get('database', '')
        try:
            pk_rows = self._execute(
                """
                SELECT TABLE_NAME AS table_name, COLUMN_NAME AS column_name
                FROM information_schema.key_column_usage
                WHERE TABLE_SCHEMA = %s AND CONSTRAINT_NAME = 'PRIMARY'
                """,
                (db,),
            )
            fk_rows = self._execute(
                """
                SELECT TABLE_NAME AS table_name, COLUMN_NAME AS column_name,
                       REFERENCED_TABLE_NAME AS referenced_table, REFERENCED_COLUMN_NAME AS referenced_column
                FROM information_schema.key_column_usage
                WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL
                """,
                (db,),
            )
        except Exception as exc:
            logger.warning('MySQL constraint discovery failed: %s', exc)
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
