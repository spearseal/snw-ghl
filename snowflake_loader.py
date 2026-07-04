"""
Snowflake Data Loader
Handles data loading and schema management in Snowflake
"""
import snowflake.connector
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import pandas as pd
from config import settings
from hipaa_compliance import hipaa_manager


class SnowflakeLoader:
    """
    Loader for Snowflake data warehouse
    Handles connection, schema creation, and data loading with HIPAA compliance
    """
    
    def __init__(self, config: Optional[Dict[str, str]] = None):
        self.config = config or {}
        self.connection = None
        self.cursor = None
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
        
        # PHI fields that need encryption
        self.phi_fields = {
            'contacts': ['email', 'phone', 'firstName', 'lastName', 'address'],
            'conversations': ['body', 'sender'],
            'opportunities': ['title', 'description']
        }
    
    def connect(self):
        """Establish connection to Snowflake using the provided config or .env defaults"""
        try:
            cfg = self.config
            self.connection = snowflake.connector.connect(
                account=cfg.get('account') or settings.snowflake_account,
                user=cfg.get('user') or settings.snowflake_user,
                password=cfg.get('password') or settings.snowflake_password,
                warehouse=(cfg.get('warehouse') or settings.snowflake_warehouse) or None,
                database=(cfg.get('database') or settings.snowflake_database) or None,
                schema=(cfg.get('schema') or settings.snowflake_schema) or None,
                role=(cfg.get('role') or settings.snowflake_role) or None,
                passcode=(cfg.get('passcode') or settings.snowflake_passcode) or None,
            )
            
            self.cursor = self.connection.cursor()
            
            self.logger.info("Successfully connected to Snowflake")
            
            hipaa_manager.log_audit_event('snowflake_connection', {
                'database': settings.snowflake_database,
                'schema': settings.snowflake_schema,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Snowflake: {e}")
            hipaa_manager.log_audit_event('snowflake_connection_error', {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
            raise
    
    def disconnect(self):
        """Close Snowflake connection"""
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.connection:
            self.connection.close()
            self.connection = None
        self.logger.info("Disconnected from Snowflake")
    
    def _create_table_if_not_exists(self, table_name: str, columns: Dict[str, str]):
        """
        Create table if it doesn't exist
        
        Args:
            table_name: Name of the table
            columns: Dictionary of column names and types
        """
        column_definitions = ', '.join([f'"{col}" {dtype}' for col, dtype in columns.items()])
        
        # Add metadata columns for HIPAA compliance
        column_definitions += ', "_sync_timestamp" TIMESTAMP_NTZ, "_data_hash" VARCHAR(64)'
        
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            {column_definitions}
        )
        """
        
        try:
            self.cursor.execute(create_table_sql)
            self.connection.commit()
            self.logger.info(f"Table {table_name} created or verified")
            
        except Exception as e:
            self.logger.error(f"Failed to create table {table_name}: {e}")
            raise
    
    def _get_table_schema(self, table_name: str) -> Dict[str, str]:
        """
        Get existing table schema from Snowflake
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary of column names and types
        """
        try:
            self.cursor.execute(f"DESCRIBE TABLE \"{table_name}\"")
            columns = {}
            for row in self.cursor.fetchall():
                col_name = row[0]
                col_type = row[1]
                # Skip metadata columns
                if not col_name.startswith('_'):
                    columns[col_name] = col_type
            return columns
        except Exception as e:
            self.logger.error(f"Failed to get schema for {table_name}: {e}")
            return {}
    
    def _encrypt_phi_data(self, data: Dict[str, Any], entity_type: str) -> Dict[str, Any]:
        """
        Encrypt PHI fields in data
        
        Args:
            data: Data dictionary
            entity_type: Type of entity (contacts, conversations, opportunities)
            
        Returns:
            Data with encrypted PHI
        """
        encrypted_data = data.copy()
        phi_fields = self.phi_fields.get(entity_type, [])
        
        for field in phi_fields:
            if field in encrypted_data and encrypted_data[field]:
                # Encrypt the PHI
                encrypted_data[field] = hipaa_manager.encrypt_data(str(encrypted_data[field]))
        
        return encrypted_data
    
    def _flatten_dict(self, data: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
        """
        Flatten nested dictionaries for Snowflake loading
        
        Args:
            data: Nested dictionary
            parent_key: Parent key for nested values
            sep: Separator for nested keys
            
        Returns:
            Flattened dictionary
        """
        items = []
        for k, v in data.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert lists to strings for storage
                items.append((new_key, str(v)))
            else:
                items.append((new_key, v))
        return dict(items)
    
    def load_contacts(self, contacts: List[Dict[str, Any]]):
        """
        Load contacts data into Snowflake
        
        Args:
            contacts: List of contact records
        """
        if not contacts:
            self.logger.warning("No contacts to load")
            return
        
        table_name = 'ghl_contacts'
        
        # Flatten and encrypt data
        processed_contacts = []
        for contact in contacts:
            flattened = self._flatten_dict(contact)
            encrypted = self._encrypt_phi_data(flattened, 'contacts')
            
            # Add metadata
            data_str = str(flattened)
            encrypted['_sync_timestamp'] = datetime.utcnow()
            encrypted['_data_hash'] = hipaa_manager.hash_phi(data_str)
            
            processed_contacts.append(encrypted)
        
        # Create DataFrame
        df = pd.DataFrame(processed_contacts)
        
        # Infer schema and create table
        schema = {}
        for col in df.columns:
            if col == '_sync_timestamp':
                schema[col] = 'TIMESTAMP_NTZ'
            elif col == '_data_hash':
                schema[col] = 'VARCHAR(64)'
            elif df[col].dtype == 'object':
                schema[col] = 'VARCHAR(16777216)'
            elif df[col].dtype == 'int64':
                schema[col] = 'NUMBER(38,0)'
            elif df[col].dtype == 'float64':
                schema[col] = 'FLOAT'
            else:
                schema[col] = 'VARCHAR(16777216)'
        
        self._create_table_if_not_exists(table_name, schema)
        
        # Load data using Snowflake's write_pandas
        try:
            from snowflake.connector.pandas_tools import write_pandas
            
            success, nchunks, nrows, _ = write_pandas(
                self.connection,
                df,
                table_name,
                quote_identifiers=False
            )
            
            self.logger.info(f"Loaded {nrows} contacts to Snowflake")
            
            hipaa_manager.log_audit_event('snowflake_data_load', {
                'table': table_name,
                'rows': nrows,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Failed to load contacts: {e}")
            hipaa_manager.log_audit_event('snowflake_load_error', {
                'table': table_name,
                'error': str(e)
            })
            raise
    
    def load_conversations(self, conversations: List[Dict[str, Any]]):
        """
        Load conversations data into Snowflake
        
        Args:
            conversations: List of conversation records
        """
        if not conversations:
            self.logger.warning("No conversations to load")
            return
        
        table_name = 'ghl_conversations'
        
        # Flatten and encrypt data
        processed_conversations = []
        for conv in conversations:
            flattened = self._flatten_dict(conv)
            encrypted = self._encrypt_phi_data(flattened, 'conversations')
            
            # Add metadata
            data_str = str(flattened)
            encrypted['_sync_timestamp'] = datetime.utcnow()
            encrypted['_data_hash'] = hipaa_manager.hash_phi(data_str)
            
            processed_conversations.append(encrypted)
        
        # Create DataFrame
        df = pd.DataFrame(processed_conversations)
        
        # Infer schema
        schema = {}
        for col in df.columns:
            if col == '_sync_timestamp':
                schema[col] = 'TIMESTAMP_NTZ'
            elif col == '_data_hash':
                schema[col] = 'VARCHAR(64)'
            elif df[col].dtype == 'object':
                schema[col] = 'VARCHAR(16777216)'
            elif df[col].dtype == 'int64':
                schema[col] = 'NUMBER(38,0)'
            elif df[col].dtype == 'float64':
                schema[col] = 'FLOAT'
            else:
                schema[col] = 'VARCHAR(16777216)'
        
        self._create_table_if_not_exists(table_name, schema)
        
        # Load data
        try:
            from snowflake.connector.pandas_tools import write_pandas
            
            success, nchunks, nrows, _ = write_pandas(
                self.connection,
                df,
                table_name,
                quote_identifiers=False
            )
            
            self.logger.info(f"Loaded {nrows} conversations to Snowflake")
            
            hipaa_manager.log_audit_event('snowflake_data_load', {
                'table': table_name,
                'rows': nrows,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Failed to load conversations: {e}")
            hipaa_manager.log_audit_event('snowflake_load_error', {
                'table': table_name,
                'error': str(e)
            })
            raise
    
    def load_opportunities(self, opportunities: List[Dict[str, Any]]):
        """
        Load opportunities data into Snowflake
        
        Args:
            opportunities: List of opportunity records
        """
        if not opportunities:
            self.logger.warning("No opportunities to load")
            return
        
        table_name = 'ghl_opportunities'
        
        # Flatten and encrypt data
        processed_opportunities = []
        for opp in opportunities:
            flattened = self._flatten_dict(opp)
            encrypted = self._encrypt_phi_data(flattened, 'opportunities')
            
            # Add metadata
            data_str = str(flattened)
            encrypted['_sync_timestamp'] = datetime.utcnow()
            encrypted['_data_hash'] = hipaa_manager.hash_phi(data_str)
            
            processed_opportunities.append(encrypted)
        
        # Create DataFrame
        df = pd.DataFrame(processed_opportunities)
        
        # Infer schema
        schema = {}
        for col in df.columns:
            if col == '_sync_timestamp':
                schema[col] = 'TIMESTAMP_NTZ'
            elif col == '_data_hash':
                schema[col] = 'VARCHAR(64)'
            elif df[col].dtype == 'object':
                schema[col] = 'VARCHAR(16777216)'
            elif df[col].dtype == 'int64':
                schema[col] = 'NUMBER(38,0)'
            elif df[col].dtype == 'float64':
                schema[col] = 'FLOAT'
            else:
                schema[col] = 'VARCHAR(16777216)'
        
        self._create_table_if_not_exists(table_name, schema)
        
        # Load data
        try:
            from snowflake.connector.pandas_tools import write_pandas
            
            success, nchunks, nrows, _ = write_pandas(
                self.connection,
                df,
                table_name,
                quote_identifiers=False
            )
            
            self.logger.info(f"Loaded {nrows} opportunities to Snowflake")
            
            hipaa_manager.log_audit_event('snowflake_data_load', {
                'table': table_name,
                'rows': nrows,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            self.logger.error(f"Failed to load opportunities: {e}")
            hipaa_manager.log_audit_event('snowflake_load_error', {
                'table': table_name,
                'error': str(e)
            })
            raise
    
    def load_all_data(self, data: Dict[str, List[Dict[str, Any]]]):
        """
        Load all data types to Snowflake
        
        Args:
            data: Dictionary containing contacts, conversations, opportunities
        """
        self.logger.info("Starting data load to Snowflake")
        
        if 'contacts' in data:
            self.load_contacts(data['contacts'])
        
        if 'conversations' in data:
            self.load_conversations(data['conversations'])
        
        if 'opportunities' in data:
            self.load_opportunities(data['opportunities'])
        
        hipaa_manager.log_audit_event('snowflake_full_load', {
            'timestamp': datetime.utcnow().isoformat()
        })
        
        self.logger.info("Completed data load to Snowflake")
