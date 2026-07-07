"""Data profiling engine."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

from semantic_layer.models import ColumnProfile, TableMetadata, TableProfile
from semantic_layer.profiling.semantics import infer_column_semantic
from semantic_layer.utils import cardinality_bucket, safe_ident

logger = logging.getLogger('semantic_layer.profiling')


def profile_table_columns(
    execute_fn: Callable[[str], List[Dict[str, Any]]],
    table: TableMetadata,
    qualified_name: str,
    sample_size: int = 1000,
    dialect: str = 'ansi',
) -> TableProfile:
    """Profile all columns in a table using SQL aggregations."""
    row_count = table.row_count
    if row_count is None:
        try:
            count_rows = execute_fn(f'SELECT COUNT(*) AS cnt FROM {qualified_name}')
            row_count = int(count_rows[0].get('cnt') or count_rows[0].get('CNT') or 0) if count_rows else 0
        except Exception as exc:
            logger.warning('Row count failed for %s: %s', table.name, exc)
            row_count = None

    profiles: List[ColumnProfile] = []
    for col in table.columns:
        profile = _profile_column(
            execute_fn=execute_fn,
            table_name=table.name,
            column_name=col.name,
            data_type=col.data_type,
            qualified_name=qualified_name,
            sample_size=sample_size,
            row_count=row_count or sample_size,
            dialect=dialect,
        )
        profiles.append(profile)

    return TableProfile(table_name=table.name, row_count=row_count, columns=profiles)


def _profile_column(
    execute_fn: Callable,
    table_name: str,
    column_name: str,
    data_type: str,
    qualified_name: str,
    sample_size: int,
    row_count: int,
    dialect: str,
) -> ColumnProfile:
    col_quoted = _quote_col(column_name, dialect)
    null_pct = 0.0
    distinct_count = None
    min_val = None
    max_val = None
    samples: List[str] = []

    try:
        stats_sql = (
            f'SELECT '
            f'COUNT(*) AS total, '
            f'SUM(CASE WHEN {col_quoted} IS NULL THEN 1 ELSE 0 END) AS nulls, '
            f'COUNT(DISTINCT {col_quoted}) AS distinct_cnt, '
            f'MIN(CAST({col_quoted} AS VARCHAR)) AS min_val, '
            f'MAX(CAST({col_quoted} AS VARCHAR)) AS max_val '
            f'FROM {qualified_name}'
        )
        if dialect == 'bigquery':
            stats_sql = stats_sql.replace('VARCHAR', 'STRING')
        rows = execute_fn(stats_sql)
        if rows:
            r = rows[0]
            total = int(r.get('total') or r.get('TOTAL') or 0)
            nulls = int(r.get('nulls') or r.get('NULLS') or 0)
            distinct_count = int(r.get('distinct_cnt') or r.get('DISTINCT_CNT') or 0)
            null_pct = (nulls / total * 100) if total else 0
            min_val = str(r.get('min_val') or r.get('MIN_VAL') or '') or None
            max_val = str(r.get('max_val') or r.get('MAX_VAL') or '') or None
    except Exception as exc:
        logger.debug('Stats query failed for %s.%s: %s', table_name, column_name, exc)

    try:
        sample_sql = (
            f'SELECT DISTINCT CAST({col_quoted} AS VARCHAR) AS val '
            f'FROM {qualified_name} WHERE {col_quoted} IS NOT NULL '
            f'LIMIT {min(sample_size, 20)}'
        )
        if dialect == 'bigquery':
            sample_sql = sample_sql.replace('VARCHAR', 'STRING')
        sample_rows = execute_fn(sample_sql)
        samples = [
            str(r.get('val') or r.get('VAL') or '')[:200]
            for r in sample_rows
            if r.get('val') or r.get('VAL')
        ]
    except Exception:
        pass

    card = cardinality_bucket(distinct_count or 0, row_count)
    semantic, conf = infer_column_semantic(column_name, data_type, samples)

    return ColumnProfile(
        column_name=column_name,
        table_name=table_name,
        null_pct=round(null_pct, 2),
        distinct_count=distinct_count,
        min_value=min_val,
        max_value=max_val,
        sample_values=samples[:5],
        cardinality=card,
        inferred_semantic=semantic,
        confidence=conf,
    )


def _quote_col(name: str, dialect: str) -> str:
    safe = safe_ident(name)
    if dialect in ('postgres', 'postgresql'):
        return f'"{safe}"'
    return safe
