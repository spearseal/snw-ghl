"""
Configuration for the semantic layer pipeline.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import settings
from semantic_layer.models import SourceType


DATA_DIR = os.environ.get(
    'DATA_DIR', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
)
SEMANTIC_OUTPUT_DIR = os.path.join(DATA_DIR, 'semantic_layer')
SEMANTIC_CONFIG_FILE = os.path.join(DATA_DIR, 'semantic_layer_config.json')


class SourceConnectorConfig(BaseModel):
    """Configuration for a single data source connector."""
    name: str
    type: SourceType
    enabled: bool = True
    config: Dict[str, str] = Field(default_factory=dict)
    profile_sample_size: int = Field(default=1000, ge=100, le=100_000)
    profile_tables: Optional[List[str]] = None  # None = all tables


class SemanticLayerConfig(BaseModel):
    """Top-level semantic layer configuration."""
    model_name: str = 'enterprise_semantic_model'
    model_description: str = 'Auto-discovered enterprise semantic layer'
    output_dir: str = SEMANTIC_OUTPUT_DIR
    max_tables_per_source: int = Field(default=200, ge=1, le=2000)
    profile_sample_size: int = Field(default=1000, ge=100, le=100_000)
    min_relationship_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    retry_attempts: int = Field(default=settings.max_retries, ge=1, le=10)
    retry_delay_seconds: float = Field(default=1.0, ge=0.1, le=30.0)
    sources: List[SourceConnectorConfig] = Field(default_factory=list)


def default_sources_from_env() -> List[SourceConnectorConfig]:
    """Build default source list from active connections and env."""
    sources: List[SourceConnectorConfig] = []

    if settings.snowflake_account and settings.snowflake_user:
        sources.append(SourceConnectorConfig(
            name='snowflake_primary',
            type=SourceType.SNOWFLAKE,
            config={
                'account': settings.snowflake_account,
                'user': settings.snowflake_user,
                'password': settings.snowflake_password,
                'warehouse': settings.snowflake_warehouse,
                'database': settings.snowflake_database,
                'schema': settings.snowflake_schema,
                'role': settings.snowflake_role or '',
                'private_key': settings.snowflake_private_key,
                'private_key_passphrase': settings.snowflake_private_key_passphrase,
                'custom_tables': settings.snowflake_custom_tables,
            },
        ))

    if settings.ghl_api_key:
        sources.append(SourceConnectorConfig(
            name='ghl_primary',
            type=SourceType.GHL,
            config={
                'api_key': settings.ghl_api_key,
                'base_url': settings.ghl_api_base_url,
                'location_id': settings.ghl_location_id or '',
                'api_version': settings.ghl_api_version,
            },
        ))

    return sources


def load_semantic_config() -> SemanticLayerConfig:
    """Load config from file or fall back to env defaults."""
    if os.path.exists(SEMANTIC_CONFIG_FILE):
        with open(SEMANTIC_CONFIG_FILE, 'r') as f:
            data = json.load(f)
        return SemanticLayerConfig.model_validate(data)

    cfg = SemanticLayerConfig(sources=default_sources_from_env())
    return cfg


def save_semantic_config(config: SemanticLayerConfig) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SEMANTIC_CONFIG_FILE, 'w') as f:
        json.dump(config.model_dump(), f, indent=2)


def resolve_semantic_config() -> SemanticLayerConfig:
    """Load config and resolve sources from DB connectors + env (Cloud Run safe)."""
    try:
        from connections import _seed_defaults, get_active_config
        _seed_defaults()
    except ImportError:
        get_active_config = None  # type: ignore

    cfg = load_semantic_config()
    resolved: List[SourceConnectorConfig] = []

    if get_active_config:
        sf = get_active_config('snowflake')
        if sf:
            resolved.append(SourceConnectorConfig(
                name='snowflake_active',
                type=SourceType.SNOWFLAKE,
                config={k: str(v) for k, v in sf.items() if v is not None},
            ))

        ghl = get_active_config('ghl')
        if ghl:
            resolved.append(SourceConnectorConfig(
                name='ghl_active',
                type=SourceType.GHL,
                config={k: str(v) for k, v in ghl.items() if v is not None},
            ))

    # Keep any non-Snowflake/GHL custom sources from saved config
    for src in cfg.sources:
        if src.type not in {SourceType.SNOWFLAKE, SourceType.GHL}:
            resolved.append(src)

    if not resolved:
        resolved = default_sources_from_env()

    cfg.sources = resolved
    return cfg


def merge_active_connection_configs(config: SemanticLayerConfig) -> SemanticLayerConfig:
    """Deprecated alias — use resolve_semantic_config()."""
    return resolve_semantic_config()
