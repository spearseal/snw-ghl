"""
Snowflake Data Reader
Reads configured Snowflake tables and decrypts PHI fields where applicable.
"""
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import snowflake.connector
from config import settings
from hipaa_compliance import hipaa_manager
from snowflake_auth import snowflake_connect


class SnowflakeReader:
    """
    Read-only access to Snowflake tables.
    Uses custom_tables from config when set, otherwise default GHL sync tables.
    """

    GHL_TABLES = {
        'contacts': 'ghl_contacts',
        'conversations': 'ghl_conversations',
        'opportunities': 'ghl_opportunities',
    }

    PHI_FIELDS = {
        'contacts': ['email', 'phone', 'firstName', 'lastName', 'address'],
        'conversations': ['body', 'sender'],
        'opportunities': ['title', 'description'],
    }

    GENERIC_PHI_FIELDS = [
        'name', 'phone', 'address', 'email', 'service',
        'firstname', 'lastname', 'body', 'description',
    ]

    _IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_$]*$')

    def __init__(self, config: Optional[Dict[str, str]] = None):
        self.config = config or {}
        self.connection = None
        self.cursor = None
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, settings.log_level, logging.INFO))

    @staticmethod
    def _parse_custom_tables(config: Dict[str, str]) -> List[str]:
        raw = (config.get('custom_tables') or settings.snowflake_custom_tables or '').strip()
        if not raw:
            return []
        return [t.strip() for t in raw.split(',') if t.strip()]

    def tables_to_fetch(self) -> Dict[str, str]:
        """Return entity_key -> table_name mapping for this connection."""
        custom = self._parse_custom_tables(self.config)
        if custom:
            return {table: table for table in custom}
        return dict(self.GHL_TABLES)

    def _safe_ident(self, name: str) -> str:
        """Validate and return an unquoted Snowflake identifier (folds to uppercase)."""
        if not self._IDENT.match(name):
            raise ValueError(f'Invalid SQL identifier: {name}')
        return name

    def _qualified_table(self, table_name: str) -> str:
        """Build DATABASE.SCHEMA.TABLE using Snowflake's default uppercase rules."""
        table = self._safe_ident(table_name)
        database = (self.config.get('database') or settings.snowflake_database or '').strip()
        schema = (self.config.get('schema') or settings.snowflake_schema or '').strip()
        if database and schema:
            return f'{self._safe_ident(database)}.{self._safe_ident(schema)}.{table}'
        if schema:
            return f'{self._safe_ident(schema)}.{table}'
        return table

    def connect(self, passcode: Optional[str] = None):
        """Establish connection to Snowflake using the provided config or .env defaults"""
        cfg = self.config
        database = cfg.get('database') or settings.snowflake_database
        schema = cfg.get('schema') or settings.snowflake_schema
        try:
            self.connection = snowflake_connect(cfg, passcode=passcode)
            self.cursor = self.connection.cursor(snowflake.connector.DictCursor)
            hipaa_manager.log_audit_event('snowflake_reader_connection', {
                'database': database,
                'schema': schema,
                'tables': list(self.tables_to_fetch().values()),
                'timestamp': datetime.utcnow().isoformat(),
            })
        except Exception as e:
            self.logger.error(f"Failed to connect to Snowflake: {e}")
            hipaa_manager.log_audit_event('snowflake_reader_connection_error', {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat(),
            })
            raise

    def disconnect(self):
        """Close Snowflake connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        self.cursor = None
        self.connection = None

    def _phi_fields_for(self, entity_type: str) -> List[str]:
        return self.PHI_FIELDS.get(entity_type, self.GENERIC_PHI_FIELDS)

    def _decrypt_row(self, row: Dict[str, Any], entity_type: str) -> Dict[str, Any]:
        """Decrypt PHI fields in a row; leave non-decryptable values untouched"""
        decrypted = dict(row)
        row_keys_lower = {str(k).lower() for k in decrypted}
        for field in self._phi_fields_for(entity_type):
            if field.lower() not in row_keys_lower:
                continue
            value = decrypted.get(field) or decrypted.get(field.upper())
            key = field if field in decrypted else field.upper()
            if value:
                try:
                    decrypted[key] = hipaa_manager.decrypt_data(str(value))
                except Exception:
                    pass
        return decrypted

    def fetch_table(self, table_name: str, limit: int = 500) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Fetch rows from a Snowflake table by name."""
        try:
            qualified = self._qualified_table(table_name)
        except ValueError as e:
            return [], str(e)

        try:
            # Unquoted identifiers — Snowflake resolves ghl_contacts -> GHL_CONTACTS
            self.cursor.execute(f'SELECT * FROM {qualified} LIMIT %s', (limit,))
            rows = self.cursor.fetchall()
        except Exception as e:
            self.logger.warning(f"Could not read {qualified}: {e}")
            return [], f'{qualified}: {e}'

        hipaa_manager.log_audit_event('snowflake_data_read', {
            'table': qualified,
            'rows': len(rows),
            'timestamp': datetime.utcnow().isoformat(),
        })

        return [self._decrypt_row(row, table_name) for row in rows], None

    def fetch_entity(self, entity_type: str, limit: int = 500) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Fetch rows for a configured entity (GHL entity key or custom table name)."""
        tables = self.tables_to_fetch()
        table = tables.get(entity_type)
        if not table:
            raise ValueError(f"Unknown entity type: {entity_type}")
        return self.fetch_table(table, limit)

    def fetch_all(self, limit_per_entity: int = 500) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, str]]:
        """Fetch all configured tables. Returns (data, table_errors)."""
        data: Dict[str, List[Dict[str, Any]]] = {}
        errors: Dict[str, str] = {}
        for entity, table in self.tables_to_fetch().items():
            rows, err = self.fetch_table(table, limit_per_entity)
            data[entity] = rows
            if err:
                errors[entity] = err
        return data, errors

    def run_query(self, sql: str) -> List[Dict[str, Any]]:
        """
        Run a read-only SQL query. Rejects any statement that is not a SELECT.
        """
        stripped = sql.strip().rstrip(';').strip()
        if not stripped.lower().startswith('select'):
            raise ValueError('Only SELECT statements are permitted')

        hipaa_manager.log_audit_event('snowflake_adhoc_query', {
            'query_hash': hipaa_manager.hash_phi(stripped),
            'timestamp': datetime.utcnow().isoformat(),
        })

        self.cursor.execute(stripped)
        rows = self.cursor.fetchall()

        decrypted_rows = []
        for row in rows:
            decrypted = dict(row)
            for field in self.GENERIC_PHI_FIELDS:
                key = field if field in decrypted else field.upper()
                value = decrypted.get(key)
                if value:
                    try:
                        decrypted[key] = hipaa_manager.decrypt_data(str(value))
                    except Exception:
                        pass
            decrypted_rows.append(decrypted)

        return decrypted_rows
