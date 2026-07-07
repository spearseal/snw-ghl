"""SQL Server connector."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from semantic_layer.connectors.sql_base import SQLConnector
from semantic_layer.models import ColumnMetadata, SourceType, TableMetadata

logger = logging.getLogger('semantic_layer.connectors.sqlserver')


class SQLServerConnector(SQLConnector):
    source_type = SourceType.SQLSERVER

    def _get_connection(self) -> Any:
        try:
            import pyodbc
        except ImportError as exc:
            raise ImportError('pyodbc is required for SQL Server. Install with: pip install pyodbc') from exc

        server = self.config.get('host') or self.config.get('server', 'localhost')
        port = self.config.get('port', '1433')
        database = self.config.get('database', '')
        user = self.config.get('user', '')
        password = self.config.get('password', '')
        driver = self.config.get('driver', 'ODBC Driver 18 for SQL Server')

        conn_str = (
            f'DRIVER={{{driver}}};SERVER={server},{port};DATABASE={database};'
            f'UID={user};PWD={password};TrustServerCertificate=yes'
        )
        return pyodbc.connect(conn_str, timeout=30)

    def connect(self, **kwargs: Any) -> None:
        self.connection = self._get_connection()
        self.cursor = self.connection.cursor()
        self._connected = True

    def _execute(self, sql: str, params=None) -> List[Dict[str, Any]]:
        self.cursor.execute(sql, params or ())
        if not self.cursor.description:
            return []
        cols = [d[0] for d in self.cursor.description]
        return [dict(zip(cols, row)) for row in self.cursor.fetchall()]

    def _discover_tables(self, database: str, schema: str, max_tables: int) -> List[TableMetadata]:
        schema = schema or 'dbo'
        rows = self._execute(
            """
            SELECT TOP (?) t.name AS table_name, p.rows AS row_count, ep.value AS comment
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            LEFT JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
            LEFT JOIN sys.extended_properties ep ON ep.major_id = t.object_id
              AND ep.minor_id = 0 AND ep.name = 'MS_Description'
            WHERE s.name = ?
            ORDER BY t.name
            """,
            (max_tables, schema),
        )
        col_rows = self._execute(
            """
            SELECT t.name AS table_name, c.name AS column_name, ty.name AS data_type,
                   c.is_nullable, c.column_id AS ordinal_position
            FROM sys.columns c
            JOIN sys.tables t ON c.object_id = t.object_id
            JOIN sys.types ty ON c.user_type_id = ty.user_type_id
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name = ?
            ORDER BY t.name, c.column_id
            """,
            (schema,),
        )
        return self._build_tables(rows, col_rows, database, schema)

    def _build_tables(self, table_rows, col_rows, database, schema) -> List[TableMetadata]:
        cols_by: Dict[str, List[ColumnMetadata]] = {}
        for row in col_rows:
            tname = row['table_name']
            cols_by.setdefault(tname, []).append(ColumnMetadata(
                name=row['column_name'],
                data_type=row['data_type'],
                nullable=bool(row['is_nullable']),
                ordinal_position=int(row.get('ordinal_position') or 0),
            ))
        return [
            TableMetadata(
                name=row['table_name'],
                database_name=database,
                schema_name=schema,
                row_count=row.get('row_count'),
                comment=str(row.get('comment') or ''),
                columns=cols_by.get(row['table_name'], []),
            )
            for row in table_rows
        ]

    def _enrich_constraints(self, tables, database, schema) -> None:
        schema = schema or 'dbo'
        try:
            pk_rows = self._execute(
                """
                SELECT t.name AS table_name, c.name AS column_name
                FROM sys.indexes i
                JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                JOIN sys.tables t ON i.object_id = t.object_id
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                WHERE i.is_primary_key = 1 AND s.name = ?
                """,
                (schema,),
            )
            fk_rows = self._execute(
                """
                SELECT tp.name AS table_name, cp.name AS column_name,
                       tr.name AS referenced_table, cr.name AS referenced_column
                FROM sys.foreign_keys fk
                JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
                JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
                JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
                JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id
                JOIN sys.schemas s ON tp.schema_id = s.schema_id
                WHERE s.name = ?
                """,
                (schema,),
            )
        except Exception as exc:
            logger.warning('SQL Server constraint discovery failed: %s', exc)
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
