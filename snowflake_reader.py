"""
Snowflake Data Reader
Reads GHL data back from Snowflake, decrypting PHI fields for authorized queries
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import snowflake.connector
from config import settings
from hipaa_compliance import hipaa_manager


class SnowflakeReader:
    """
    Read-only access to the GHL tables stored in Snowflake.
    Decrypts PHI fields via the HIPAA compliance manager and logs every access.
    """

    TABLES = {
        'contacts': 'ghl_contacts',
        'conversations': 'ghl_conversations',
        'opportunities': 'ghl_opportunities',
    }

    PHI_FIELDS = {
        'contacts': ['email', 'phone', 'firstName', 'lastName', 'address'],
        'conversations': ['body', 'sender'],
        'opportunities': ['title', 'description'],
    }

    def __init__(self):
        self.connection = None
        self.cursor = None
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, settings.log_level, logging.INFO))

    def connect(self):
        """Establish connection to Snowflake"""
        self.connection = snowflake.connector.connect(
            account=settings.snowflake_account,
            user=settings.snowflake_user,
            password=settings.snowflake_password,
            warehouse=settings.snowflake_warehouse,
            database=settings.snowflake_database,
            schema=settings.snowflake_schema,
            role=settings.snowflake_role,
        )
        self.cursor = self.connection.cursor(snowflake.connector.DictCursor)
        hipaa_manager.log_audit_event('snowflake_reader_connection', {
            'database': settings.snowflake_database,
            'schema': settings.snowflake_schema,
            'timestamp': datetime.utcnow().isoformat(),
        })

    def disconnect(self):
        """Close Snowflake connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        self.cursor = None
        self.connection = None

    def _decrypt_row(self, row: Dict[str, Any], entity_type: str) -> Dict[str, Any]:
        """Decrypt PHI fields in a row; leave non-decryptable values untouched"""
        decrypted = dict(row)
        for field in self.PHI_FIELDS.get(entity_type, []):
            value = decrypted.get(field) or decrypted.get(field.upper())
            key = field if field in decrypted else field.upper()
            if value:
                try:
                    decrypted[key] = hipaa_manager.decrypt_data(str(value))
                except Exception:
                    # Value may not be encrypted (legacy rows); keep as-is
                    pass
        return decrypted

    def fetch_entity(self, entity_type: str, limit: int = 500) -> List[Dict[str, Any]]:
        """
        Fetch rows for an entity type from Snowflake with PHI decrypted.

        Args:
            entity_type: One of contacts, conversations, opportunities
            limit: Max rows to fetch

        Returns:
            List of row dictionaries
        """
        table = self.TABLES.get(entity_type)
        if not table:
            raise ValueError(f"Unknown entity type: {entity_type}")

        try:
            self.cursor.execute(f'SELECT * FROM "{table}" LIMIT %s', (limit,))
            rows = self.cursor.fetchall()
        except Exception as e:
            self.logger.warning(f"Could not read {table}: {e}")
            return []

        hipaa_manager.log_audit_event('snowflake_data_read', {
            'table': table,
            'rows': len(rows),
            'timestamp': datetime.utcnow().isoformat(),
        })

        return [self._decrypt_row(row, entity_type) for row in rows]

    def fetch_all(self, limit_per_entity: int = 500) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch all GHL entities from Snowflake"""
        return {
            entity: self.fetch_entity(entity, limit_per_entity)
            for entity in self.TABLES
        }

    def run_query(self, sql: str) -> List[Dict[str, Any]]:
        """
        Run a read-only SQL query. Rejects any statement that is not a SELECT.

        Args:
            sql: SQL statement

        Returns:
            List of row dictionaries
        """
        stripped = sql.strip().rstrip(';').strip()
        if not stripped.lower().startswith('select'):
            raise ValueError('Only SELECT statements are permitted')

        hipaa_manager.log_audit_event('snowflake_adhoc_query', {
            'query_hash': hipaa_manager.hash_phi(stripped),
            'timestamp': datetime.utcnow().isoformat(),
        })

        self.cursor.execute(stripped)
        return self.cursor.fetchall()
