"""
Marketing insights computed from GoHighLevel and Snowflake datasets.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DATE_FIELDS = (
    'lastActivity', 'last_activity', 'LAST_ACTIVITY',
    'dateUpdated', 'date_updated', 'DATE_UPDATED', 'updatedAt', 'UPDATED_AT',
    'dateAdded', 'date_added', 'DATE_ADDED', 'createdAt', 'CREATED_AT',
    'DATE_CREATED', 'last_message_date', 'LAST_MESSAGE_DATE',
    'lastStatusChangeAt', 'lastStageChangeAt', 'lastActionDate',
)

FOLLOWUP_FIELDS = (
    'last_message_date', 'LAST_MESSAGE_DATE', 'lastActivity', 'last_activity',
    'LAST_ACTIVITY', 'lastActionDate', 'LAST_ACTION_DATE',
)

NAME_FIELDS = ('firstName', 'first_name', 'FIRST_NAME', 'name', 'NAME')
EMAIL_FIELDS = ('email', 'EMAIL', 'emailAddress', 'EMAIL_ADDRESS')
PHONE_FIELDS = ('phone', 'PHONE', 'phoneNumber', 'PHONE_NUMBER')


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace('Z', '+00:00')
    try:
        if text.isdigit():
            ts = int(text)
            if ts > 1_000_000_000_000:
                ts //= 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        return datetime.fromisoformat(text)
    except (ValueError, OSError, OverflowError):
        return None


def _field(record: Dict[str, Any], names: Tuple[str, ...]) -> Any:
    for name in names:
        if name in record and record[name] not in (None, ''):
            return record[name]
        upper = name.upper()
        if upper in record and record[upper] not in (None, ''):
            return record[upper]
        lower = name.lower()
        if lower in record and record[lower] not in (None, ''):
            return record[lower]
    return None


def _days_since(record: Dict[str, Any], fields: Tuple[str, ...]) -> Optional[int]:
    best: Optional[datetime] = None
    for field in fields:
        dt = _parse_dt(record.get(field))
        if dt and (best is None or dt > best):
            best = dt
    if not best:
        return None
    return max(0, (datetime.now(timezone.utc) - best).days)


def _contact_name(record: Dict[str, Any]) -> str:
    first = _field(record, ('firstName', 'first_name', 'FIRST_NAME')) or ''
    last = _field(record, ('lastName', 'last_name', 'LAST_NAME')) or ''
    full = f'{first} {last}'.strip()
    if full:
        return full
    return str(_field(record, NAME_FIELDS) or 'Unknown')


def _normalize_contact(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    contact_id = (
        record.get('id') or record.get('ID') or record.get('contactId')
        or record.get('CONTACT_ID') or ''
    )
    return {
        'id': str(contact_id),
        'name': _contact_name(record),
        'email': _field(record, EMAIL_FIELDS),
        'phone': _field(record, PHONE_FIELDS),
        'source': source,
        'days_inactive': _days_since(record, DATE_FIELDS),
        'days_since_followup': _days_since(record, FOLLOWUP_FIELDS),
        'tags': record.get('tags') or record.get('TAGS') or [],
    }


def _is_inactive_no_followup(contact: Dict[str, Any], threshold_days: int = 90) -> bool:
    inactive = contact.get('days_inactive')
    since_followup = contact.get('days_since_followup')
    if inactive is None and since_followup is None:
        return False
    inactive_days = inactive if inactive is not None else since_followup or 0
    followup_days = since_followup if since_followup is not None else inactive_days
    return inactive_days >= threshold_days and followup_days >= threshold_days


def _sum_pipeline(opportunities: List[Dict[str, Any]]) -> float:
    total = 0.0
    for opp in opportunities:
        status = str(
            opp.get('status') or opp.get('STATUS') or ''
        ).lower()
        if status and status not in ('open', 'active', ''):
            continue
        value = (
            opp.get('monetaryValue') or opp.get('monetary_value')
            or opp.get('MONETARY_VALUE') or opp.get('value') or opp.get('VALUE') or 0
        )
        try:
            total += float(value)
        except (TypeError, ValueError):
            continue
    return total


def _count_by_status(opportunities: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {'open': 0, 'won': 0, 'lost': 0, 'other': 0}
    for opp in opportunities:
        status = str(opp.get('status') or opp.get('STATUS') or 'other').lower()
        if status in counts:
            counts[status] += 1
        else:
            counts['other'] += 1
    return counts


def _new_contacts_30d(contacts: List[Dict[str, Any]]) -> int:
    count = 0
    for contact in contacts:
        days = _days_since(contact, ('dateAdded', 'date_added', 'DATE_ADDED', 'createdAt', 'DATE_CREATED'))
        if days is not None and days <= 30:
            count += 1
    return count


def _kpi(
    key: str,
    label: str,
    value: Any,
    *,
    source: str,
    detail: str = '',
    trend: Optional[str] = None,
    format_as: str = 'number',
) -> Dict[str, Any]:
    return {
        'key': key,
        'label': label,
        'value': value,
        'source': source,
        'detail': detail,
        'trend': trend,
        'format': format_as,
    }


def compute_insights(
    datasets: Dict[str, Dict[str, List[Dict[str, Any]]]],
    connected: Dict[str, bool],
    inactive_days: int = 90,
    mask_contacts: bool = True,
) -> Dict[str, Any]:
    """Build marketing KPI cards and follow-up candidate lists from loaded datasets."""
    ghl = datasets.get('ghl') or {}
    snowflake = datasets.get('snowflake') or {}

    ghl_contacts = ghl.get('contacts') or []
    ghl_opps = ghl.get('opportunities') or []
    ghl_convs = ghl.get('conversations') or []

    sf_contacts = (
        snowflake.get('contacts') or snowflake.get('ghl_contacts') or []
    )
    sf_opps = (
        snowflake.get('opportunities') or snowflake.get('ghl_opportunities') or []
    )
    sf_convs = (
        snowflake.get('conversations') or snowflake.get('ghl_conversations') or []
    )

    ghl_norm = [_normalize_contact(c, 'ghl') for c in ghl_contacts]
    sf_norm = [_normalize_contact(c, 'snowflake') for c in sf_contacts]

    ghl_inactive = [c for c in ghl_norm if _is_inactive_no_followup(c, inactive_days)]
    sf_inactive = [c for c in sf_norm if _is_inactive_no_followup(c, inactive_days)]

    ghl_opp_stats = _count_by_status(ghl_opps)
    sf_opp_stats = _count_by_status(sf_opps)

    snoozed = sum(
        1 for c in ghl_convs + sf_convs
        if str(c.get('status') or c.get('STATUS') or '').lower() == 'snoozed'
    )
    unread = sum(
        int(c.get('unreadCount') or c.get('unread_count') or c.get('UNREAD_COUNT') or 0)
        for c in ghl_convs + sf_convs
    )

    kpis: List[Dict[str, Any]] = []

    if connected.get('ghl'):
        kpis.extend([
            _kpi(
                'ghl_contacts',
                'GHL Contacts',
                len(ghl_contacts),
                source='GoHighLevel',
                detail='Live CRM contact records',
            ),
            _kpi(
                'ghl_open_pipeline',
                'GHL Open Pipeline',
                f'${_sum_pipeline(ghl_opps):,.0f}',
                source='GoHighLevel',
                detail=f'{ghl_opp_stats["open"]} open opportunities',
                format_as='currency',
            ),
            _kpi(
                'ghl_new_contacts',
                'GHL New Contacts (30d)',
                _new_contacts_30d(ghl_contacts),
                source='GoHighLevel',
                detail='Contacts added in the last 30 days',
            ),
            _kpi(
                'ghl_inactive_followup',
                'GHL No-Show / No Follow-up',
                len(ghl_inactive),
                source='GoHighLevel',
                detail=f'Inactive ≥ {inactive_days} days with no follow-up',
                trend='attention' if ghl_inactive else None,
            ),
        ])

    if connected.get('snowflake'):
        kpis.extend([
            _kpi(
                'sf_contacts',
                'Snowflake Contacts',
                len(sf_contacts),
                source='Snowflake',
                detail='Rows in ghl_contacts / contacts tables',
            ),
            _kpi(
                'sf_open_pipeline',
                'Snowflake Open Pipeline',
                f'${_sum_pipeline(sf_opps):,.0f}',
                source='Snowflake',
                detail=f'{sf_opp_stats["open"]} open opportunities',
                format_as='currency',
            ),
            _kpi(
                'sf_won_deals',
                'Snowflake Won Deals',
                sf_opp_stats['won'],
                source='Snowflake',
                detail='Closed-won opportunities in warehouse',
            ),
            _kpi(
                'sf_inactive_followup',
                'Snowflake Stale Contacts',
                len(sf_inactive),
                source='Snowflake',
                detail=f'No activity ≥ {inactive_days} days',
                trend='attention' if sf_inactive else None,
            ),
        ])

    if connected.get('ghl') and connected.get('snowflake'):
        total_contacts = len(ghl_contacts) + len(sf_contacts)
        total_inactive = len(ghl_inactive) + len(sf_inactive)
        kpis.insert(0, _kpi(
            'combined_reach',
            'Total Audience Reach',
            total_contacts,
            source='GoHighLevel + Snowflake',
            detail='Combined contact records across connected sources',
        ))
        kpis.insert(1, _kpi(
            'combined_followup',
            'Re-engagement Opportunities',
            total_inactive,
            source='GoHighLevel + Snowflake',
            detail=f'Customers with ≥ {inactive_days} days no show / no follow-up',
            trend='attention' if total_inactive else None,
        ))

    if snoozed or unread:
        kpis.append(_kpi(
            'engagement_queue',
            'Engagement Queue',
            snoozed + unread,
            source='GoHighLevel + Snowflake' if connected.get('ghl') and connected.get('snowflake') else (
                'GoHighLevel' if connected.get('ghl') else 'Snowflake'
            ),
            detail=f'{snoozed} snoozed conversations, {unread} unread messages',
        ))

    # Deduplicate inactive candidates by email when possible
    seen_emails: set = set()
    followup_candidates: List[Dict[str, Any]] = []
    for contact in ghl_inactive + sf_inactive:
        email = (contact.get('email') or '').strip().lower()
        if email and email in seen_emails:
            continue
        if email:
            seen_emails.add(email)
        entry = dict(contact)
        if mask_contacts:
            entry['email'] = hipaa_manager_mask(entry.get('email'))
            entry['phone'] = hipaa_manager_mask(entry.get('phone'))
        followup_candidates.append(entry)

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'connected_sources': connected,
        'inactive_days_threshold': inactive_days,
        'kpis': kpis,
        'followup_candidates': followup_candidates[:100],
        'followup_candidate_count': len(ghl_inactive) + len(sf_inactive),
        'summary': {
            'ghl': {
                'contacts': len(ghl_contacts),
                'opportunities': len(ghl_opps),
                'conversations': len(ghl_convs),
                'inactive_no_followup': len(ghl_inactive),
            },
            'snowflake': {
                'contacts': len(sf_contacts),
                'opportunities': len(sf_opps),
                'conversations': len(sf_convs),
                'inactive_no_followup': len(sf_inactive),
            },
        },
    }


def hipaa_manager_mask(value: Any) -> Optional[str]:
    if value is None or value == '':
        return None
    from hipaa_compliance import hipaa_manager
    return hipaa_manager.mask_sensitive_data(str(value))
