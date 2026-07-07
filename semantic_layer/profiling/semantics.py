"""Column semantic inference from name, type, and sample values."""
from __future__ import annotations

import re
from typing import List, Tuple

from semantic_layer.models import ColumnSemantic

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
_PHONE_RE = re.compile(r'^[\d\s\-\+\(\)]{7,20}$')
_CURRENCY_RE = re.compile(r'^[\$\€\£]?\s?[\d,]+\.?\d*$')
_DATE_TYPES = {'date', 'timestamp', 'timestamp_ntz', 'timestamp_ltz', 'timestamp_tz', 'datetime', 'timestamptz'}
_STATUS_WORDS = {'active', 'inactive', 'pending', 'open', 'closed', 'won', 'lost', 'draft', 'published'}


def infer_column_semantic(
    column_name: str,
    data_type: str,
    sample_values: List[str],
) -> Tuple[ColumnSemantic, float]:
    """Infer business meaning for a column. Returns (semantic, confidence)."""
    name = column_name.lower()
    dtype = data_type.lower()

    # ID columns
    if name == 'id' or name.endswith('_id') or name.endswith('id') and len(name) > 2:
        if name.endswith('_id') or name != 'id':
            return ColumnSemantic.FOREIGN_KEY, 0.85
        return ColumnSemantic.ID, 0.9

    # Email
    if 'email' in name:
        return ColumnSemantic.EMAIL, 0.95
    if sample_values and sum(1 for v in sample_values if _EMAIL_RE.match(v)) >= len(sample_values) * 0.7:
        return ColumnSemantic.EMAIL, 0.8

    # Phone
    if any(k in name for k in ('phone', 'mobile', 'fax', 'tel')):
        return ColumnSemantic.PHONE, 0.9
    if sample_values and sum(1 for v in sample_values if _PHONE_RE.match(v)) >= len(sample_values) * 0.6:
        return ColumnSemantic.PHONE, 0.75

    # Dates
    if any(k in name for k in ('date', 'time', 'created', 'updated', 'modified', 'timestamp')):
        return ColumnSemantic.DATETIME, 0.85
    if any(t in dtype for t in _DATE_TYPES):
        return ColumnSemantic.DATE, 0.9

    # Currency / amounts
    if any(k in name for k in ('amount', 'price', 'cost', 'revenue', 'value', 'total', 'monetary')):
        return ColumnSemantic.CURRENCY, 0.85
    if sample_values and sum(1 for v in sample_values if _CURRENCY_RE.match(v)) >= len(sample_values) * 0.5:
        return ColumnSemantic.CURRENCY, 0.7

    # Status
    if any(k in name for k in ('status', 'state', 'stage', 'phase')):
        return ColumnSemantic.STATUS, 0.9
    if sample_values:
        lower_vals = {v.lower() for v in sample_values if v}
        if lower_vals and lower_vals.issubset(_STATUS_WORDS | {v.lower() for v in sample_values}):
            if len(lower_vals) <= 10:
                return ColumnSemantic.STATUS, 0.75

    # Name fields
    if any(k in name for k in ('name', 'firstname', 'lastname', 'first_name', 'last_name', 'title')):
        return ColumnSemantic.NAME, 0.85

    # Address
    if any(k in name for k in ('address', 'street', 'city', 'zip', 'postal', 'country')):
        return ColumnSemantic.ADDRESS, 0.85

    # Boolean
    if dtype in ('boolean', 'bool', 'bit') or name.startswith('is_') or name.startswith('has_'):
        return ColumnSemantic.BOOLEAN, 0.85

    # Category / low cardinality text
    if sample_values and len(set(sample_values)) <= 20 and len(sample_values) >= 5:
        return ColumnSemantic.CATEGORY, 0.6

    # Numeric measures
    if any(t in dtype for t in ('int', 'float', 'double', 'decimal', 'number', 'numeric')):
        if not is_id_column_name(name):
            return ColumnSemantic.MEASURE, 0.7

    # Text
    if any(t in dtype for t in ('varchar', 'text', 'string', 'char')):
        return ColumnSemantic.TEXT, 0.5

    return ColumnSemantic.UNKNOWN, 0.3


def is_id_column_name(name: str) -> bool:
    n = name.lower()
    return n == 'id' or n.endswith('_id')
