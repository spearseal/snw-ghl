"""
Configuration management for GHL-Snowflake integration
Handles environment variables and settings with validation
"""
import os
from typing import Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings with validation"""
    
    # GoHighLevel Configuration
    ghl_api_key: str = Field(default="", env="GHL_API_KEY")
    ghl_api_base_url: str = Field(
        default="https://services.leadconnectorhq.com",
        env="GHL_API_BASE_URL"
    )
    ghl_location_id: Optional[str] = Field(None, env="GHL_LOCATION_ID")
    
    # Snowflake Configuration
    snowflake_account: str = Field(default="", env="SNOWFLAKE_ACCOUNT")
    snowflake_user: str = Field(default="", env="SNOWFLAKE_USER")
    snowflake_password: str = Field(default="", env="SNOWFLAKE_PASSWORD")
    snowflake_warehouse: str = Field(default="", env="SNOWFLAKE_WAREHOUSE")
    snowflake_database: str = Field(default="", env="SNOWFLAKE_DATABASE")
    snowflake_schema: str = Field(default="PUBLIC", env="SNOWFLAKE_SCHEMA")
    snowflake_role: Optional[str] = Field(None, env="SNOWFLAKE_ROLE")
    
    # Security Configuration
    encryption_key: str = Field(default="", env="ENCRYPTION_KEY")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    audit_log_enabled: bool = Field(default=True, env="AUDIT_LOG_ENABLED")
    audit_log_path: str = Field(default="./logs/audit.log", env="AUDIT_LOG_PATH")
    
    # Data Sync Configuration
    sync_interval_minutes: int = Field(default=60, env="SYNC_INTERVAL_MINUTES")
    batch_size: int = Field(default=100, env="BATCH_SIZE")
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    
    @validator('encryption_key')
    def validate_encryption_key(cls, v):
        """Validate encryption key is 32 bytes for AES-256, or generate a default for POC"""
        if not v:
            return 'ghl_snowflake_poc_key_2024_!!!!!'[:32]
        if len(v) != 32:
            raise ValueError('Encryption key must be exactly 32 characters for AES-256')
        return v
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of {valid_levels}')
        return v.upper()
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False


# Global settings instance
settings = Settings()
