"""
Snowflake schema discovery via INFORMATION_SCHEMA.
"""
from typing import Any, Dict, List, Optional

from config import settings


def discover_schema(reader) -> Dict[str, Any]:
    """
    List tables and columns in the connection's configured database and schema.

    Args:
        reader: Connected SnowflakeReader instance
    """
    database = (reader.config.get('database') or settings.snowflake_database or '').strip()
    schema = (reader.config.get('schema') or settings.snowflake_schema or '').strip()
    if not database or not schema:
        raise ValueError('Database and schema must be configured on the Snowflake connection')

    db = reader._safe_ident(database)
    sch = reader._safe_ident(schema)

    reader.cursor.execute(
        """
        SELECT table_name, row_count, comment
        FROM information_schema.tables
        WHERE table_catalog = %s
          AND table_schema = %s
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """,
        (db.upper(), sch.upper()),
    )
    table_rows = reader.cursor.fetchall()

    reader.cursor.execute(
        """
        SELECT table_name, column_name, data_type, is_nullable, comment
        FROM information_schema.columns
        WHERE table_catalog = %s
          AND table_schema = %s
        ORDER BY table_name, ordinal_position
        """,
        (db.upper(), sch.upper()),
    )
    column_rows = reader.cursor.fetchall()

    columns_by_table: Dict[str, List[Dict[str, str]]] = {}
    for row in column_rows:
        table = row['TABLE_NAME']
        columns_by_table.setdefault(table, []).append({
            'name': row['COLUMN_NAME'],
            'type': row['DATA_TYPE'],
            'nullable': row['IS_NULLABLE'],
            'comment': row.get('COMMENT') or '',
        })

    tables: List[Dict[str, Any]] = []
    for row in table_rows:
        name = row['TABLE_NAME']
        tables.append({
            'name': name,
            'row_count': row.get('ROW_COUNT'),
            'comment': row.get('COMMENT') or '',
            'columns': columns_by_table.get(name, []),
        })

    return {
        'database': database,
        'schema': schema,
        'qualified_prefix': f'{db}.{sch}',
        'table_count': len(tables),
        'tables': tables,
    }
