"""
Query Engine
Builds a searchable index over GoHighLevel and Snowflake data using Chonkie
for chunking, and answers free-text questions with BM25 ranked retrieval.
"""
import logging
import math
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from chonkie import RecursiveChunker

from config import settings
from hipaa_compliance import hipaa_manager


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


SNOWFLAKE_HINTS = frozenset({
    'snowflake', 'warehouse', 'database', 'schema', 'sql', 'table', 'tables', 'column',
})
GHL_HINTS = frozenset({
    'ghl', 'gohighlevel', 'highlevel', 'leadconnector', 'crm', 'pipeline', 'location',
})


def detect_query_sources(question: str, available: List[str]) -> List[str]:
    """Pick which sources to query. Defaults to all available unless the question names one."""
    if not available:
        return []
    if len(available) == 1:
        return available

    q_lower = question.lower()
    tokens = set(_tokenize(question))
    wants_snowflake = bool(tokens & SNOWFLAKE_HINTS) or 'from snowflake' in q_lower
    wants_ghl = (
        bool(tokens & GHL_HINTS)
        or 'from ghl' in q_lower
        or 'from gohighlevel' in q_lower
        or 'from go high level' in q_lower
    )

    if wants_snowflake and not wants_ghl and 'snowflake' in available:
        return ['snowflake']
    if wants_ghl and not wants_snowflake and 'ghl' in available:
        return ['ghl']
    return available


class QueryEngine:
    """
    In-memory retrieval engine.

    - Converts GHL / Snowflake records into text documents
    - Chunks them with Chonkie's RecursiveChunker
    - Ranks chunks against a query with BM25
    - Returns masked, audit-logged answers
    """

    def __init__(self, chunk_size: int = 512):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
        self.chunker = RecursiveChunker(chunk_size=chunk_size)
        self.chunks: List[Dict[str, Any]] = []
        self._doc_freq: Counter = Counter()
        self._avg_len: float = 0.0
        self.last_indexed: Optional[str] = None
        self.record_counts: Dict[str, Dict[str, int]] = {}

    def get_indexed_sources(self) -> List[str]:
        return sorted({c['source'] for c in self.chunks})

    def _rebuild_doc_freq(self):
        self._doc_freq = Counter()
        for chunk in self.chunks:
            self._doc_freq.update(set(chunk['tokens'].keys()))
        total_len = sum(c['length'] for c in self.chunks)
        self._avg_len = total_len / len(self.chunks) if self.chunks else 0.0

    # ------------------------------------------------------------------ #
    # Indexing
    # ------------------------------------------------------------------ #
    def _record_to_text(self, record: Dict[str, Any]) -> str:
        """Render a record as readable 'key: value' lines"""
        lines = []
        for key, value in record.items():
            if value is None or str(value).strip() in ('', '[]', '{}', 'None'):
                continue
            if str(key).startswith('_'):
                continue
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def index_data(
        self,
        datasets: Dict[str, Dict[str, List[Dict[str, Any]]]],
        merge: bool = False,
    ):
        """
        Build the chunk index.

        Args:
            datasets: {'ghl': {'contacts': [...], ...}, 'snowflake': {...}}
            merge: When True, replace only the provided sources and keep others.
        """
        if merge:
            replace_sources = set(datasets.keys())
            self.chunks = [c for c in self.chunks if c['source'] not in replace_sources]
            for source in replace_sources:
                self.record_counts.pop(source, None)
        else:
            self.chunks = []
            self.record_counts = {}

        for source, entities in datasets.items():
            counts = {
                entity: len(records or [])
                for entity, records in (entities or {}).items()
            }
            self.record_counts[source] = counts

            for entity_type, records in (entities or {}).items():
                for record in records or []:
                    text = self._record_to_text(record)
                    if not text:
                        continue
                    for chunk in self.chunker.chunk(text):
                        tokens = _tokenize(chunk.text)
                        if not tokens:
                            continue
                        self.chunks.append({
                            'source': source,
                            'entity': entity_type,
                            'record_id': record.get('id') or record.get('ID'),
                            'text': chunk.text,
                            'tokens': Counter(tokens),
                            'length': len(tokens),
                        })

        self._rebuild_doc_freq()
        self.last_indexed = datetime.utcnow().isoformat()

        hipaa_manager.log_audit_event('query_index_built', {
            'chunks': len(self.chunks),
            'sources': self.get_indexed_sources(),
            'timestamp': self.last_indexed,
        })
        self.logger.info(f"Indexed {len(self.chunks)} chunks from {self.get_indexed_sources()}")

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #
    def _bm25_score(self, query_tokens: List[str], chunk: Dict[str, Any],
                    k1: float = 1.5, b: float = 0.75) -> float:
        score = 0.0
        n_docs = len(self.chunks)
        for token in query_tokens:
            tf = chunk['tokens'].get(token, 0)
            if tf == 0:
                continue
            df = self._doc_freq.get(token, 0)
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            denom = tf + k1 * (1 - b + b * chunk['length'] / (self._avg_len or 1))
            score += idf * (tf * (k1 + 1)) / denom
        return score

    def _count_summary(self, sources: Optional[List[str]] = None) -> Optional[str]:
        active_sources = sources or self.get_indexed_sources()
        parts: List[str] = []
        total = 0
        for source in active_sources:
            for entity, count in (self.record_counts.get(source) or {}).items():
                if count:
                    total += count
                    parts.append(f'{count} in {entity}')
        if not parts:
            return None
        return f'Total records in memory: {total} ({", ".join(parts)})'

    def query(
        self,
        question: str,
        top_k: int = 5,
        mask_phi: bool = True,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Answer a free-text question from the indexed data.

        Args:
            question: Natural language question
            top_k: Number of chunks to return
            mask_phi: Mask email/phone patterns in output
            sources: Optional list of sources to search (snowflake, ghl)

        Returns:
            Dict with answer summary and supporting results
        """
        hipaa_manager.log_audit_event('query_executed', {
            'query_hash': hipaa_manager.hash_phi(question),
            'timestamp': datetime.utcnow().isoformat(),
        })

        searchable = self.chunks
        if sources:
            searchable = [c for c in self.chunks if c['source'] in sources]

        if not searchable:
            if not self.chunks:
                return {
                    'answer': 'No data in memory yet. Connect a datasource and run a query.',
                    'results': [],
                    'total_chunks': 0,
                    'searched_sources': sources or [],
                    'indexed_sources': self.get_indexed_sources(),
                }
            label = ', '.join(sources or [])
            return {
                'answer': f'No data indexed for {label}. Connect that source and query again.',
                'results': [],
                'total_chunks': len(self.chunks),
                'searched_sources': sources or [],
                'indexed_sources': self.get_indexed_sources(),
            }

        count_answer = None
        if re.search(r'\b(how many|total|count|number of)\b', question, re.I):
            count_answer = self._count_summary(sources)
            if count_answer and re.search(
                r'\b(customers?|contacts?|records?|rows?|entries)\b', question, re.I
            ):
                return {
                    'answer': count_answer,
                    'results': [],
                    'total_chunks': len(self.chunks),
                    'searched_sources': sources or self.get_indexed_sources(),
                    'indexed_sources': self.get_indexed_sources(),
                }

        query_tokens = _tokenize(question)
        scored = [
            (self._bm25_score(query_tokens, chunk), chunk)
            for chunk in searchable
        ]
        scored = [item for item in scored if item[0] > 0]
        scored.sort(key=lambda item: item[0], reverse=True)
        top = scored[:top_k]

        results = []
        for score, chunk in top:
            text = chunk['text']
            if mask_phi:
                text = self._mask_phi_patterns(text)
            results.append({
                'score': round(score, 4),
                'source': chunk['source'],
                'entity': chunk['entity'],
                'record_id': hipaa_manager.mask_sensitive_data(str(chunk['record_id'] or '')),
                'text': text,
            })

        if results:
            result_sources = sorted({r['source'] for r in results})
            source_labels = {
                'snowflake': 'Snowflake',
                'ghl': 'GoHighLevel',
            }
            names = [source_labels.get(s, s) for s in result_sources]
            answer = (
                f"Found {len(results)} relevant record(s) from "
                f"{', '.join(names)}. "
                f"Top match: {source_labels.get(results[0]['source'], results[0]['source'])} "
                f"/ {results[0]['entity']}."
            )
            if count_answer:
                answer = f'{count_answer}. {answer}'
        else:
            searched = ', '.join(sources) if sources else 'connected sources'
            answer = count_answer or f'No matching records found in {searched} for your question.'

        return {
            'answer': answer,
            'results': results,
            'total_chunks': len(self.chunks),
            'searched_sources': sources or self.get_indexed_sources(),
            'indexed_sources': self.get_indexed_sources(),
        }

    @staticmethod
    def _mask_phi_patterns(text: str) -> str:
        """Mask common PHI patterns (emails, phone numbers, SSNs) in output"""
        text = re.sub(
            r"[\w.+-]+@[\w-]+\.[\w.]+",
            lambda m: hipaa_manager.mask_sensitive_data(m.group(0)),
            text,
        )
        text = re.sub(
            r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",
            '***-**-****',
            text,
        )
        text = re.sub(
            r"\+?\d[\d\s().-]{8,}\d",
            lambda m: hipaa_manager.mask_sensitive_data(m.group(0)),
            text,
        )
        return text
