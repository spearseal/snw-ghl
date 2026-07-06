"""
Global search across contacts and opportunities with pagination-friendly indexing.
"""
from __future__ import annotations

from typing import Any, Dict, List

from insights import _contact_name, _field, EMAIL_FIELDS, PHONE_FIELDS


def _match_query(text: str, query: str) -> bool:
    return query.lower() in (text or '').lower()


def search_datasets(
    datasets: Dict[str, Dict[str, List[Dict[str, Any]]]],
    query: str,
    *,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    q = query.strip()
    if not q:
        return {'results': [], 'total': 0, 'limit': limit, 'offset': offset}

    hits: List[Dict[str, Any]] = []

    ghl = datasets.get('ghl') or {}
    snowflake = datasets.get('snowflake') or {}

    for source_key, bucket in (('ghl', ghl), ('snowflake', snowflake)):
        contacts = bucket.get('contacts') or bucket.get('ghl_contacts') or []
        for record in contacts:
            name = _contact_name(record)
            email = str(_field(record, EMAIL_FIELDS) or '')
            phone = str(_field(record, PHONE_FIELDS) or '')
            cid = str(record.get('id') or record.get('ID') or '')
            if not any(_match_query(v, q) for v in (name, email, phone, cid)):
                continue
            hits.append({
                'id': cid,
                'type': 'contact',
                'title': name,
                'subtitle': email or phone or None,
                'source': 'GoHighLevel' if source_key == 'ghl' else 'Snowflake',
            })

        opps = bucket.get('opportunities') or bucket.get('ghl_opportunities') or []
        for record in opps:
            title = str(
                record.get('name') or record.get('NAME') or record.get('title') or 'Opportunity'
            )
            status = str(record.get('status') or record.get('STATUS') or '')
            oid = str(record.get('id') or record.get('ID') or '')
            if not any(_match_query(v, q) for v in (title, status, oid)):
                continue
            hits.append({
                'id': oid,
                'type': 'opportunity',
                'title': title,
                'subtitle': status or None,
                'source': 'GoHighLevel' if source_key == 'ghl' else 'Snowflake',
            })

    total = len(hits)
    page = hits[offset: offset + limit]
    return {
        'results': page,
        'total': total,
        'limit': limit,
        'offset': offset,
        'query': q,
    }
