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

    def index_data(self, datasets: Dict[str, Dict[str, List[Dict[str, Any]]]]):
        """
        Build the chunk index.

        Args:
            datasets: {'ghl': {'contacts': [...], ...}, 'snowflake': {...}}
        """
        self.chunks = []
        self._doc_freq = Counter()

        for source, entities in datasets.items():
            for entity_type, records in (entities or {}).items():
                for record in records:
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
                        self._doc_freq.update(set(tokens))

        total_len = sum(c['length'] for c in self.chunks)
        self._avg_len = total_len / len(self.chunks) if self.chunks else 0.0
        self.last_indexed = datetime.utcnow().isoformat()

        hipaa_manager.log_audit_event('query_index_built', {
            'chunks': len(self.chunks),
            'timestamp': self.last_indexed,
        })
        self.logger.info(f"Indexed {len(self.chunks)} chunks")

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

    def query(self, question: str, top_k: int = 5,
              mask_phi: bool = True) -> Dict[str, Any]:
        """
        Answer a free-text question from the indexed data.

        Args:
            question: Natural language question
            top_k: Number of chunks to return
            mask_phi: Mask email/phone patterns in output

        Returns:
            Dict with answer summary and supporting results
        """
        hipaa_manager.log_audit_event('query_executed', {
            'query_hash': hipaa_manager.hash_phi(question),
            'timestamp': datetime.utcnow().isoformat(),
        })

        if not self.chunks:
            return {
                'answer': 'No data indexed yet. Run a sync or refresh the index first.',
                'results': [],
                'total_chunks': 0,
            }

        query_tokens = _tokenize(question)
        scored = [
            (self._bm25_score(query_tokens, chunk), chunk)
            for chunk in self.chunks
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
            answer = (
                f"Found {len(results)} relevant record(s) "
                f"across {len({r['source'] for r in results})} data source(s). "
                f"Top match is from {results[0]['source']} / {results[0]['entity']}."
            )
        else:
            answer = 'No matching records found for your query.'

        return {
            'answer': answer,
            'results': results,
            'total_chunks': len(self.chunks),
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
