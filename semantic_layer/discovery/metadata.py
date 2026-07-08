"""Metadata discovery orchestration."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from semantic_layer.config import SourceConnectorConfig
from semantic_layer.connectors.registry import create_connector
from semantic_layer.models import SourceMetadata
from semantic_layer.utils import setup_logging

logger = setup_logging()


def discover_source_metadata(
    source_config: SourceConnectorConfig,
    max_tables: int = 200,
    passcode: Optional[str] = None,
) -> SourceMetadata:
    """Discover metadata from a single configured source."""
    connector = create_connector(source_config)
    try:
        connect_kwargs = {}
        if passcode:
            connect_kwargs['passcode'] = passcode
        connector.connect(**connect_kwargs)
        metadata = connector.discover_metadata(max_tables=max_tables)
        logger.info(
            'Discovered %d tables and %d views from %s',
            len(metadata.tables), len(metadata.views), source_config.name,
        )
        return metadata
    finally:
        connector.disconnect()


def discover_all_sources(
    sources: List[SourceConnectorConfig],
    max_tables: int = 200,
    passcode: Optional[str] = None,
) -> Tuple[List[SourceMetadata], Dict[str, str]]:
    """Discover metadata from all enabled sources. Returns (results, errors_by_source)."""
    results: List[SourceMetadata] = []
    errors: Dict[str, str] = {}

    if not sources:
        return results, {'config': 'No sources in semantic layer configuration'}

    for src in sources:
        if not src.enabled:
            logger.info('Skipping disabled source: %s', src.name)
            continue
        try:
            meta = discover_source_metadata(src, max_tables=max_tables, passcode=passcode)
            results.append(meta)
        except Exception as exc:
            msg = str(exc)
            logger.error('Discovery failed for %s: %s', src.name, exc)
            errors[src.name] = msg

    return results, errors


def discover_all_sources_list(
    sources: List[SourceConnectorConfig],
    max_tables: int = 200,
    passcode: Optional[str] = None,
) -> List[SourceMetadata]:
    """Backwards-compatible wrapper returning only metadata list."""
    results, _ = discover_all_sources(sources, max_tables=max_tables, passcode=passcode)
    return results
