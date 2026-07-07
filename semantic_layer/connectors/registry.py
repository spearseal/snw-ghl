"""Connector registry — factory for all supported source types."""
from __future__ import annotations

import logging
from typing import Dict, Type

from semantic_layer.config import SourceConnectorConfig
from semantic_layer.connectors.base import BaseConnector
from semantic_layer.models import SourceType

logger = logging.getLogger('semantic_layer.connectors.registry')

_REGISTRY: Dict[SourceType, Type[BaseConnector]] | None = None


def _connector_registry() -> Dict[SourceType, Type[BaseConnector]]:
    """Lazy-load connector classes to keep app startup fast."""
    global _REGISTRY
    if _REGISTRY is not None:
        return _REGISTRY

    from semantic_layer.connectors.bigquery import BigQueryConnector
    from semantic_layer.connectors.ghl import GHLConnector
    from semantic_layer.connectors.mysql import MySQLConnector
    from semantic_layer.connectors.postgresql import PostgreSQLConnector
    from semantic_layer.connectors.rest_api import RestApiConnector
    from semantic_layer.connectors.snowflake import SnowflakeConnector
    from semantic_layer.connectors.sqlserver import SQLServerConnector

    _REGISTRY = {
        SourceType.SNOWFLAKE: SnowflakeConnector,
        SourceType.BIGQUERY: BigQueryConnector,
        SourceType.POSTGRESQL: PostgreSQLConnector,
        SourceType.SQLSERVER: SQLServerConnector,
        SourceType.MYSQL: MySQLConnector,
        SourceType.REST_API: RestApiConnector,
        SourceType.GHL: GHLConnector,
    }
    return _REGISTRY


def get_connector_registry() -> Dict[SourceType, Type[BaseConnector]]:
    return _connector_registry()


def create_connector(source_config: SourceConnectorConfig) -> BaseConnector:
    """Instantiate a connector from configuration."""
    registry = _connector_registry()
    cls = registry.get(source_config.type)
    if not cls:
        raise ValueError(f'Unsupported source type: {source_config.type}')
    return cls(name=source_config.name, config=source_config.config)


def list_supported_sources() -> list[str]:
    return [t.value for t in _connector_registry()]
