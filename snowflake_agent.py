"""
Schema-aware Snowflake agent: discovers tables in the configured database/schema
and answers natural-language prompts with read-only SQL.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import settings
from hipaa_compliance import hipaa_manager
from snowflake_schema import discover_schema

logger = logging.getLogger(__name__)

_COUNT_RE = re.compile(r'\b(how many|total|count|number of)\b', re.I)
_BROAD_RE = re.compile(r'\b(all columns|everything|full details|complete record|entire row)\b', re.I)

_TOPIC_KEYWORDS = {
    'customer': ['customer', 'customers', 'contact', 'contacts', 'client', 'clients'],
    'conversation': ['conversation', 'conversations', 'message', 'messages', 'chat'],
    'opportunity': ['opportunity', 'opportunities', 'deal', 'deals', 'pipeline'],
    'service': ['service', 'services'],
}

# Map question terms to likely column name fragments.
_COLUMN_SYNONYMS: Dict[str, List[str]] = {
    'phone': ['phone', 'mobile', 'cell', 'tel'],
    'email': ['email', 'mail'],
    'name': ['name', 'firstname', 'lastname', 'first_name', 'last_name'],
    'address': ['address', 'street', 'city', 'zip'],
    'message': ['message', 'body', 'last_message_body', 'text', 'content'],
    'status': ['status', 'state'],
    'channel': ['channel', 'medium'],
    'unread': ['unread', 'unread_count'],
    'contact': ['contact_id', 'contact'],
    'conversation': ['conversation_id', 'conversation'],
    'date': ['date', 'created', 'updated', 'timestamp'],
    'direction': ['direction', 'last_message_direction'],
    'service': ['service'],
    'title': ['title', 'subject'],
    'amount': ['amount', 'value', 'price', 'revenue'],
}


def _extract_select_columns(sql: str) -> Optional[List[str]]:
    """Parse column names from a simple SELECT statement (not SELECT *)."""
    match = re.search(r'^\s*select\s+(distinct\s+)?(.+?)\s+from\s+', sql, re.I | re.DOTALL)
    if not match:
        return None
    clause = match.group(2).strip()
    if clause == '*':
        return None
    columns: List[str] = []
    for part in clause.split(','):
        part = part.strip()
        if not part:
            continue
        # Handle COUNT(*) AS TOTAL, expressions, table.col
        alias_match = re.search(r'\bas\s+([a-zA-Z_][\w$]*)\s*$', part, re.I)
        if alias_match:
            columns.append(alias_match.group(1).upper())
            continue
        col = part.split()[-1]
        col = col.split('.')[-1]
        columns.append(col.upper())
    return columns or None


def _filter_rows_by_columns(
    rows: List[Dict[str, Any]],
    columns: Optional[List[str]],
) -> List[Dict[str, Any]]:
    if not columns or not rows:
        return rows
    allowed = {c.upper() for c in columns}
    filtered = []
    for row in rows:
        subset = {
            k: v for k, v in row.items()
            if str(k).upper() in allowed
        }
        if subset:
            filtered.append(subset)
    return filtered or rows


def _pick_columns(question: str, table: Dict[str, Any]) -> Optional[List[str]]:
    """
    Return specific column names when the question asks for particular fields.
    Returns None to mean SELECT * (broad question).
    """
    if _BROAD_RE.search(question):
        return None

    q_lower = question.lower()
    tokens = set(_tokenize(question))
    matched: List[str] = []

    for col in table['columns']:
        col_name = col['name']
        col_lower = col_name.lower()
        col_parts = col_lower.split('_')

        if col_lower in q_lower or col_lower in tokens:
            matched.append(col_name)
            continue

        if any(part in tokens for part in col_parts if len(part) > 2):
            matched.append(col_name)
            continue

        for _term, synonyms in _COLUMN_SYNONYMS.items():
            if any(syn in tokens or syn in q_lower for syn in synonyms):
                if any(syn in col_lower for syn in synonyms):
                    matched.append(col_name)

    # Deduplicate preserving order
    seen = set()
    unique = []
    for col in matched:
        key = col.upper()
        if key not in seen:
            seen.add(key)
            unique.append(col)

    if not unique:
        return None

    # Always include a stable id column when present and we're being selective
    id_cols = [c['name'] for c in table['columns'] if c['name'].upper().endswith('_ID')]
    for id_col in id_cols[:1]:
        if id_col not in unique:
            unique.insert(0, id_col)

    return unique


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _schema_text(schema: Dict[str, Any], max_tables: int = 40) -> str:
  """Compact schema summary for LLM or logging."""
  lines = [
      f"Database: {schema['database']}, Schema: {schema['schema']}",
      f"Tables ({schema['table_count']}):",
  ]
  for table in schema['tables'][:max_tables]:
      cols = ', '.join(c['name'] for c in table['columns'][:30])
      rc = table.get('row_count')
      rc_txt = f', ~{rc} rows' if rc is not None else ''
      lines.append(f"- {table['name']}{rc_txt}: [{cols}]")
  return '\n'.join(lines)


def _score_table(question: str, table: Dict[str, Any]) -> float:
    q = question.lower()
    tokens = set(_tokenize(question))
    name = table['name'].lower()
    score = 0.0

    if name in q:
        score += 20
    for part in name.split('_'):
        if part and part in tokens:
            score += 6

    for col in table['columns']:
        col_name = col['name'].lower()
        if col_name in tokens:
            score += 4
        for part in col_name.split('_'):
            if part and part in tokens:
                score += 2

    for keywords in _TOPIC_KEYWORDS.values():
        if any(kw in q for kw in keywords) and any(kw in name for kw in keywords):
            score += 8

    if 'ghl_contacts' in name and any(k in q for k in ('customer', 'contact')):
        score += 10
    if table.get('row_count'):
        score += min(float(table['row_count']), 50) * 0.01

    return score


def _pick_table(question: str, schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not schema['tables']:
        return None
    scored = sorted(
        (( _score_table(question, t), t) for t in schema['tables']),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, best = scored[0]
    if best_score <= 0:
        return schema['tables'][0]
    return best


def _qualified_table(schema: Dict[str, Any], table_name: str) -> str:
    return f"{schema['qualified_prefix']}.{table_name}"


def _heuristic_sql(question: str, schema: Dict[str, Any], limit: int) -> Tuple[str, str]:
    table = _pick_table(question, schema)
    if not table:
        raise ValueError(f"No tables found in {schema['database']}.{schema['schema']}")

    qualified = _qualified_table(schema, table['name'])
    reasoning = (
        f"Analyzed {schema['table_count']} table(s) in "
        f"{schema['database']}.{schema['schema']}. "
        f"Best match for your question: {table['name']}."
    )

    if _COUNT_RE.search(question):
        sql = f"SELECT COUNT(*) AS TOTAL FROM {qualified}"
        reasoning += ' Generated a COUNT query.'
        return sql, reasoning

    columns = _pick_columns(question, table)
    if columns:
        col_list = ', '.join(columns)
        sql = f"SELECT {col_list} FROM {qualified} LIMIT {int(limit)}"
        reasoning += f' Selected columns: {", ".join(columns)}.'
    else:
        sql = f"SELECT * FROM {qualified} LIMIT {int(limit)}"
        reasoning += f' Returned all columns (broad question). LIMIT {limit}.'
    return sql, reasoning


def _llm_sql(question: str, schema: Dict[str, Any], limit: int) -> Optional[Tuple[str, str]]:
    groq_key = (settings.groq_api_key or '').strip()
    openai_key = (settings.openai_api_key or '').strip()

    if groq_key:
        api_key = groq_key
        base_url = 'https://api.groq.com/openai/v1/chat/completions'
        model = settings.groq_model
        provider = 'groq'
    elif openai_key:
        api_key = openai_key
        base_url = 'https://api.openai.com/v1/chat/completions'
        model = settings.openai_model
        provider = 'openai'
    else:
        return None

    prefix = schema['qualified_prefix']
    system = (
        'You are a Snowflake SQL expert. Given a database schema and a user question, '
        'write exactly one read-only SELECT statement. '
        f'Always fully qualify tables as {prefix}.TABLE_NAME (unquoted identifiers). '
        'IMPORTANT: Select ONLY the specific columns needed to answer the question. '
        'Do NOT use SELECT * unless the user explicitly asks for all columns, '
        'everything, full details, or a complete report. '
        'If they ask about messages, select message/body columns only. '
        'If they ask about status, select status columns only. '
        'Include an ID column only when useful for context. '
        f'Never use INSERT, UPDATE, DELETE, DROP, or DDL. '
        f'Use LIMIT {limit} when returning rows. '
        'Respond with JSON only: {"sql": "...", "reasoning": "...", "columns": ["COL1", "COL2"]}'
    )
    user = f"Schema:\n{_schema_text(schema)}\n\nQuestion: {question}"

    try:
        resp = requests.post(
            base_url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': user},
                ],
                'temperature': 0,
                'response_format': {'type': 'json_object'},
            },
            timeout=45,
        )
        resp.raise_for_status()
        content = resp.json()['choices'][0]['message']['content']
        data = json.loads(content)
        sql = (data.get('sql') or '').strip()
        reasoning = data.get('reasoning') or f'Generated SQL via {provider} from schema context.'
        if sql.lower().startswith('select'):
            return sql, reasoning
    except Exception as exc:
        logger.warning(f"LLM SQL generation failed ({provider}), using heuristics: {exc}")
    return None


def _validate_sql(sql: str) -> str:
    stripped = sql.strip().rstrip(';').strip()
    lowered = stripped.lower()
    if not lowered.startswith('select'):
        raise ValueError('Only SELECT statements are permitted')
    forbidden = ('insert ', 'update ', 'delete ', 'drop ', 'alter ', 'create ', 'truncate ', 'merge ')
    if any(word in lowered for word in forbidden):
        raise ValueError('Only read-only SELECT statements are permitted')
    return stripped


class SnowflakeAgent:
    """Discover schema and answer NL questions with SQL."""

    def __init__(self, reader):
        self.reader = reader
        self.schema: Optional[Dict[str, Any]] = None

    def analyze_schema(self, refresh: bool = False) -> Dict[str, Any]:
        if self.schema is None or refresh:
            self.schema = discover_schema(self.reader)
        return self.schema

    def query(
        self,
        question: str,
        limit: int = 100,
        mask_phi: bool = True,
    ) -> Dict[str, Any]:
        schema = self.analyze_schema(refresh=True)
        hipaa_manager.log_audit_event('snowflake_agent_query', {
            'query_hash': hipaa_manager.hash_phi(question),
            'database': schema['database'],
            'schema': schema['schema'],
            'table_count': schema['table_count'],
        })

        if schema['table_count'] == 0:
            return {
                'answer': (
                    f"No tables found in {schema['database']}.{schema['schema']}. "
                    'Check database/schema on the connection or grant USAGE/SELECT.'
                ),
                'sql': None,
                'reasoning': 'Schema discovery returned zero tables.',
                'schema': schema,
                'rows': [],
                'row_count': 0,
            }

        llm_result = _llm_sql(question, schema, limit)
        if llm_result:
            sql, reasoning = llm_result
            method = 'llm'
        else:
            sql, reasoning = _heuristic_sql(question, schema, limit)
            method = 'heuristic'

        sql = _validate_sql(sql)
        rows = self.reader.run_query(sql)

        selected_columns = _extract_select_columns(sql)
        rows = _filter_rows_by_columns(rows, selected_columns)

        if mask_phi:
            rows = [self._mask_row(row) for row in rows]

        answer = self._format_answer(question, sql, rows, schema, reasoning, selected_columns)

        return {
            'answer': answer,
            'sql': sql,
            'reasoning': reasoning,
            'method': method,
            'columns': selected_columns or (list(rows[0].keys()) if rows else []),
            'schema_summary': {
                'database': schema['database'],
                'schema': schema['schema'],
                'table_count': schema['table_count'],
                'tables': [t['name'] for t in schema['tables']],
            },
            'rows': rows[:limit],
            'row_count': len(rows),
        }

    @staticmethod
    def _mask_row(row: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(row)
        for key, value in out.items():
            if value is None:
                continue
            key_lower = str(key).lower()
            if any(p in key_lower for p in ('email', 'phone', 'address', 'name', 'ssn')):
                out[key] = hipaa_manager.mask_sensitive_data(str(value))
        return out

    @staticmethod
    def _format_answer(
        question: str,
        sql: str,
        rows: List[Dict[str, Any]],
        schema: Dict[str, Any],
        reasoning: str,
        columns: Optional[List[str]] = None,
    ) -> str:
        if not rows:
            return (
                f"Query ran successfully against {schema['database']}.{schema['schema']} "
                'but returned 0 rows.'
            )
        if len(rows) == 1 and 'TOTAL' in rows[0]:
            total = rows[0]['TOTAL']
            return f"Total: {total} record(s) in the matched table."
        col_txt = ''
        if columns:
            col_txt = f" Columns: {', '.join(columns)}."
        elif rows:
            col_txt = f" Columns: {', '.join(str(k) for k in rows[0].keys())}."
        return (
            f"Found {len(rows)} row(s) from {schema['database']}.{schema['schema']}."
            f"{col_txt}"
        )
