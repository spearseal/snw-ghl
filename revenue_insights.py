"""
Monthly revenue growth metrics and decision factors from GHL + Snowflake data.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from insights import (
    DATE_FIELDS,
    _count_by_status,
    _days_since,
    _is_inactive_no_followup,
    _new_contacts_30d,
    _normalize_contact,
    _parse_dt,
    _sum_pipeline,
)

IMPACT_ORDER = {'high': 0, 'medium': 1, 'low': 2}


def _month_key(dt: datetime) -> str:
    return dt.strftime('%Y-%m')


def _record_month(record: Dict[str, Any], fields: Tuple[str, ...]) -> Optional[str]:
    best: Optional[datetime] = None
    for field in fields:
        dt = _parse_dt(record.get(field))
        if dt and (best is None or dt > best):
            best = dt
    return _month_key(best) if best else None


def _opp_status(opp: Dict[str, Any]) -> str:
    return str(opp.get('status') or opp.get('STATUS') or 'other').lower()


def _opp_value(opp: Dict[str, Any]) -> float:
    value = (
        opp.get('monetaryValue') or opp.get('monetary_value')
        or opp.get('MONETARY_VALUE') or opp.get('value') or 0
    )
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _month_range(months: int) -> List[str]:
    now = datetime.now(timezone.utc)
    keys: List[str] = []
    year, month = now.year, now.month
    for _ in range(months):
        keys.append(f'{year:04d}-{month:02d}')
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(keys))


def _factor(
    key: str,
    label: str,
    value: Any,
    impact: str,
    recommendation: str,
    trend: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        'key': key,
        'label': label,
        'value': value,
        'impact': impact,
        'recommendation': recommendation,
        'trend': trend,
    }


def _build_month_factors(
    month_data: Dict[str, Any],
    prev_month: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    factors: List[Dict[str, Any]] = []

    open_pipeline = month_data.get('open_pipeline_value', 0)
    won_revenue = month_data.get('won_revenue', 0)
    new_contacts = month_data.get('new_contacts', 0)
    stale = month_data.get('stale_opportunities', 0)
    inactive = month_data.get('inactive_patients', 0)
    lost = month_data.get('lost_count', 0)
    won = month_data.get('won_count', 0)

    prev_won = (prev_month or {}).get('won_revenue', 0)
    revenue_delta = won_revenue - prev_won if prev_won else None

    factors.append(_factor(
        'won_revenue',
        'Closed revenue',
        f'${won_revenue:,.0f}',
        'high' if won_revenue > 0 else 'medium',
        'Celebrate wins in team huddle; document what closed each deal.',
        trend='up' if revenue_delta and revenue_delta > 0 else ('down' if revenue_delta and revenue_delta < 0 else None),
    ))

    factors.append(_factor(
        'open_pipeline',
        'Open pipeline value',
        f'${open_pipeline:,.0f}',
        'high' if open_pipeline > 10000 else 'medium',
        'Prioritize consult bookings for top 5 open opportunities this week.',
    ))

    if stale:
        factors.append(_factor(
            'stale_pipeline',
            'Stalled deals (14+ days)',
            stale,
            'high' if stale >= 3 else 'medium',
            'Call stalled consults personally — each day of delay reduces close rate.',
            trend='attention',
        ))

    if new_contacts:
        factors.append(_factor(
            'new_leads',
            'New patient leads',
            new_contacts,
            'medium',
            'First touch within 48 hours increases consult show-rate by 2–3×.',
        ))

    if inactive:
        factors.append(_factor(
            'inactive_patients',
            'Lapsed patients',
            inactive,
            'high' if inactive >= 5 else 'medium',
            'Launch a win-back email/SMS campaign before month-end.',
            trend='attention' if inactive else None,
        ))

    close_rate = round(won / max(won + lost, 1) * 100)
    factors.append(_factor(
        'close_rate',
        'Win rate',
        f'{close_rate}%',
        'high' if close_rate < 40 else 'low',
        'Review lost deals for pricing/objection patterns; adjust consult script.',
    ))

    factors.sort(key=lambda f: IMPACT_ORDER.get(f['impact'], 9))
    return factors[:6]


def compute_revenue_growth(
    datasets: Dict[str, Dict[str, List[Dict[str, Any]]]],
    connected: Dict[str, bool],
    months: int = 12,
    inactive_days: int = 90,
) -> Dict[str, Any]:
    ghl = datasets.get('ghl') or {}
    snowflake = datasets.get('snowflake') or {}

    contacts = (
        (ghl.get('contacts') or [])
        + (snowflake.get('contacts') or snowflake.get('ghl_contacts') or [])
    )
    opportunities = (
        (ghl.get('opportunities') or [])
        + (snowflake.get('opportunities') or snowflake.get('ghl_opportunities') or [])
    )

    month_keys = _month_range(months)
    monthly: Dict[str, Dict[str, Any]] = {
        k: {
            'month': k,
            'new_contacts': 0,
            'won_revenue': 0.0,
            'won_count': 0,
            'lost_count': 0,
            'open_pipeline_value': 0.0,
            'open_count': 0,
            'stale_opportunities': 0,
            'inactive_patients': 0,
        }
        for k in month_keys
    }

    created_fields = ('dateAdded', 'date_added', 'DATE_ADDED', 'createdAt', 'CREATED_AT', 'DATE_CREATED')
    updated_fields = ('dateUpdated', 'date_updated', 'DATE_UPDATED', 'updatedAt', 'UPDATED_AT', 'lastStageChangeAt')

    for contact in contacts:
        month = _record_month(contact, created_fields)
        if month in monthly:
            monthly[month]['new_contacts'] += 1

    current_open_pipeline = _sum_pipeline(opportunities)
    open_count = _count_by_status(opportunities)['open']

    for opp in opportunities:
        status = _opp_status(opp)
        value = _opp_value(opp)
        month = _record_month(opp, updated_fields) or _record_month(opp, created_fields)

        if status == 'won' and month in monthly:
            monthly[month]['won_revenue'] += value
            monthly[month]['won_count'] += 1
        elif status == 'lost' and month in monthly:
            monthly[month]['lost_count'] += 1
        elif status in ('open', 'active', ''):
            stale_days = _days_since(opp, DATE_FIELDS)
            if stale_days is not None and stale_days >= 14:
                target = month_keys[-1]
                monthly[target]['stale_opportunities'] += 1

    norm_contacts = []
    for c in contacts[:500]:
        source = 'snowflake' if c in (snowflake.get('contacts') or snowflake.get('ghl_contacts') or []) else 'ghl'
        norm_contacts.append(_normalize_contact(c, source))

    inactive_count = sum(1 for c in norm_contacts if _is_inactive_no_followup(c, inactive_days))
    monthly[month_keys[-1]]['inactive_patients'] = inactive_count
    monthly[month_keys[-1]]['open_pipeline_value'] = round(current_open_pipeline, 2)
    monthly[month_keys[-1]]['open_count'] = open_count

    monthly_list: List[Dict[str, Any]] = []
    prev: Optional[Dict[str, Any]] = None
    for key in month_keys:
        entry = dict(monthly[key])
        entry['decision_factors'] = _build_month_factors(entry, prev)
        monthly_list.append(entry)
        prev = entry

    current = monthly_list[-1] if monthly_list else {}
    current_factors = current.get('decision_factors', [])

    total_won_ytd = sum(m['won_revenue'] for m in monthly_list)
    total_new = sum(m['new_contacts'] for m in monthly_list)

    sources = []
    if connected.get('ghl'):
        sources.append('GoHighLevel')
    if connected.get('snowflake'):
        sources.append('Snowflake')

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'connected_sources': connected,
        'source_label': ' + '.join(sources) if sources else 'No source connected',
        'months_analyzed': months,
        'summary': {
            'current_month': month_keys[-1] if month_keys else None,
            'current_open_pipeline': round(current_open_pipeline, 2),
            'current_open_deals': open_count,
            'ytd_won_revenue': round(total_won_ytd, 2),
            'ytd_new_contacts': total_new,
            'inactive_patients': inactive_count,
        },
        'monthly': monthly_list,
        'current_month_factors': current_factors,
        'message': (
            None if contacts or opportunities else
            'Connect data sources and refresh to see revenue growth factors.'
        ),
    }
