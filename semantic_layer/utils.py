"""
Shared utilities: logging, retry, naming helpers.
"""
from __future__ import annotations

import logging
import re
import time
from functools import wraps
from typing import Any, Callable, List, Optional, TypeVar

from config import settings

logger = logging.getLogger('semantic_layer')

T = TypeVar('T')

_IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_$]*$')


def setup_logging() -> logging.Logger:
    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
    return logger


def retry(
    attempts: int = 3,
    delay: float = 1.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """Decorator with exponential backoff retry."""
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exc: Optional[Exception] = None
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < attempts:
                        wait = delay * (2 ** (attempt - 1))
                        logger.warning(
                            '%s failed (attempt %d/%d): %s — retrying in %.1fs',
                            fn.__name__, attempt, attempts, exc, wait,
                        )
                        time.sleep(wait)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


def safe_ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f'Invalid SQL identifier: {name}')
    return name


def to_snake_case(name: str) -> str:
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    s = re.sub(r'[\s\-\.]+', '_', s)
    return s.lower().strip('_')


def to_business_name(name: str) -> str:
    """Convert snake_case / camelCase to Title Case business name."""
    snake = to_snake_case(name)
    return ' '.join(w.capitalize() for w in snake.split('_') if w)


def singularize(name: str) -> str:
    n = name.lower()
    if n.endswith('ies'):
        return n[:-3] + 'y'
    if n.endswith('ses') or n.endswith('xes'):
        return n[:-2]
    if n.endswith('s') and not n.endswith('ss'):
        return n[:-1]
    return n


def pluralize(name: str) -> str:
    n = name.lower()
    if n.endswith('y') and len(n) > 1 and n[-2] not in 'aeiou':
        return n[:-1] + 'ies'
    if n.endswith(('s', 'x', 'z', 'ch', 'sh')):
        return n + 'es'
    if not n.endswith('s'):
        return n + 's'
    return n


def is_id_column(name: str) -> bool:
    n = name.lower()
    return n == 'id' or n.endswith('_id') or n.endswith('id') and len(n) > 2


def is_lookup_table(table_name: str, column_count: int, row_count: Optional[int]) -> bool:
    """Heuristic: small tables with few columns are likely lookups."""
    if row_count is not None and row_count > 10_000:
        return False
    if column_count > 15:
        return False
    name = table_name.lower()
    lookup_hints = ('lookup', 'ref_', 'dim_', 'code', 'type', 'status', 'category')
    return any(h in name for h in lookup_hints) or (column_count <= 6 and (row_count or 0) < 500)


def cardinality_bucket(distinct: int, total: int) -> str:
    if total <= 0:
        return 'medium'
    ratio = distinct / total
    if ratio >= 0.99:
        return 'unique'
    if ratio >= 0.5:
        return 'high'
    if ratio <= 0.05:
        return 'low'
    return 'medium'
