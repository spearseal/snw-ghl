"""
Connector abstraction for semantic layer source systems.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from semantic_layer.models import (
    ColumnMetadata,
    ConstraintMetadata,
    SourceMetadata,
    SourceType,
    TableMetadata,
    TableProfile,
)


class BaseConnector(ABC):
    """Abstract connector for metadata discovery and profiling."""

    source_type: SourceType

    def __init__(self, name: str, config: Dict[str, str]):
        self.name = name
        self.config = config
        self._connected = False

    @abstractmethod
    def connect(self, **kwargs: Any) -> None:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    def discover_metadata(self, max_tables: int = 200) -> SourceMetadata:
        ...

    @abstractmethod
    def profile_table(
        self,
        table: TableMetadata,
        sample_size: int = 1000,
    ) -> TableProfile:
        ...

    def test_connection(self) -> bool:
        try:
            self.connect()
            self.disconnect()
            return True
        except Exception:
            return False

    def __enter__(self) -> 'BaseConnector':
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()
