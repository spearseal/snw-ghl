"""
Medspa CEO priorities and customer-service compliance evaluation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from insights import (
    DATE_FIELDS,
    FOLLOWUP_FIELDS,
    _count_by_status,
    _days_since,
    _is_inactive_no_followup,
    _new_contacts_30d,
    _normalize_contact,
    _sum_pipeline,
    hipaa_manager_mask,
)


def _priority(rank: int) -> str:
    if rank <= 2:
        return 'high'
    if rank <= 4:
        return 'medium'
    return 'low'


def compute_ceo_tasks(
    datasets: Dict[str, Dict[str, List[Dict[str, Any]]]],
    connected: Dict[str, bool],
    inactive_days: int = 90,
) -> List[Dict[str, Any]]:
    """
    Top 5 prioritized tasks for a medspa CEO based on live GHL + Snowflake data.
    """
    ghl = datasets.get('ghl') or {}
    snowflake = datasets.get('snowflake') or {}

    ghl_contacts = ghl.get('contacts') or []
    ghl_opps = ghl.get('opportunities') or []
    ghl_convs = ghl.get('conversations') or []
    sf_contacts = snowflake.get('contacts') or snowflake.get('ghl_contacts') or []
    sf_opps = snowflake.get('opportunities') or snowflake.get('ghl_opportunities') or []
    sf_convs = snowflake.get('conversations') or snowflake.get('ghl_conversations') or []

    ghl_norm = [_normalize_contact(c, 'ghl') for c in ghl_contacts]
    sf_norm = [_normalize_contact(c, 'snowflake') for c in sf_contacts]
    inactive = [c for c in ghl_norm + sf_norm if _is_inactive_no_followup(c, inactive_days)]

    snoozed = sum(
        1 for c in ghl_convs + sf_convs
        if str(c.get('status') or c.get('STATUS') or '').lower() == 'snoozed'
    )
    unread = sum(
        int(c.get('unreadCount') or c.get('unread_count') or c.get('UNREAD_COUNT') or 0)
        for c in ghl_convs + sf_convs
    )
    backlog = snoozed + unread

    open_pipeline = _sum_pipeline(ghl_opps) + _sum_pipeline(sf_opps)
    open_count = _count_by_status(ghl_opps)['open'] + _count_by_status(sf_opps)['open']

    new_contacts = _new_contacts_30d(ghl_contacts) + _new_contacts_30d(sf_contacts)
    new_without_followup = _count_new_without_nurture(ghl_contacts + sf_contacts)

    missing_contact_info = _count_missing_contact_channels(ghl_norm + sf_norm)

    sources = []
    if connected.get('ghl'):
        sources.append('GoHighLevel')
    if connected.get('snowflake'):
        sources.append('Snowflake')
    source_label = ' + '.join(sources) if sources else 'No source connected'

    candidates: List[Dict[str, Any]] = [
        {
            'score': len(inactive) * 10 + (50 if inactive else 0),
            'title': 'Re-engage lapsed patients',
            'description': (
                f'{len(inactive)} patient(s) have had no show or no follow-up for '
                f'{inactive_days}+ days. Launch a re-engagement campaign before they churn.'
            ),
            'metric': len(inactive),
            'metric_label': 'patients at risk',
            'category': 'retention',
            'action': 'Open Email Follow-up in the bottom taskbar and send a win-back sequence.',
            'source': source_label,
        },
        {
            'score': backlog * 8 + (40 if backlog else 0),
            'title': 'Clear the patient messaging backlog',
            'description': (
                f'{backlog} conversation item(s) need attention '
                f'({snoozed} snoozed, {unread} unread). Medspa patients expect same-day responses.'
            ),
            'metric': backlog,
            'metric_label': 'open conversations',
            'category': 'customer_service',
            'action': 'Review snoozed and unread threads in GoHighLevel and assign to front desk.',
            'source': source_label,
        },
        {
            'score': int(open_pipeline / 500) + open_count * 5,
            'title': 'Push open consult & treatment pipeline',
            'description': (
                f'${open_pipeline:,.0f} in open pipeline across {open_count} opportunity(ies). '
                'Book consults and close treatment plans this week.'
            ),
            'metric': f'${open_pipeline:,.0f}',
            'metric_label': 'pipeline value',
            'category': 'revenue',
            'action': 'Call or text top open opportunities and offer limited-time consult slots.',
            'source': source_label,
        },
        {
            'score': new_without_followup * 6 + new_contacts,
            'title': 'Nurture new leads within 48 hours',
            'description': (
                f'{new_contacts} new contact(s) in the last 30 days; '
                f'{new_without_followup} still need a first follow-up touch.'
            ),
            'metric': new_without_followup,
            'metric_label': 'leads awaiting nurture',
            'category': 'acquisition',
            'action': 'Send welcome SMS or email and book a complimentary skin consult.',
            'source': source_label,
        },
        {
            'score': missing_contact_info * 5 + 30,
            'title': 'Run compliance & service quality audit',
            'description': (
                f'{missing_contact_info} record(s) lack email or phone for HIPAA-safe follow-up. '
                'Open Compliance in the bottom taskbar for a full evaluation and recommendations.'
            ),
            'metric': missing_contact_info,
            'metric_label': 'data gaps',
            'category': 'compliance',
            'action': 'Open Compliance service → review findings → schedule recommended follow-ups.',
            'source': source_label,
        },
    ]

    candidates.sort(key=lambda t: t['score'], reverse=True)
    tasks: List[Dict[str, Any]] = []
    for i, task in enumerate(candidates[:5], start=1):
        tasks.append({
            'rank': i,
            'priority': _priority(i),
            'title': task['title'],
            'description': task['description'],
            'metric': task['metric'],
            'metric_label': task['metric_label'],
            'category': task['category'],
            'action': task['action'],
            'source': task['source'],
        })
    return tasks


def _count_new_without_nurture(contacts: List[Dict[str, Any]], nurture_days: int = 2) -> int:
    count = 0
    for contact in contacts:
        added_days = _days_since(contact, ('dateAdded', 'date_added', 'DATE_ADDED', 'createdAt', 'DATE_CREATED'))
        if added_days is None or added_days > 30:
            continue
        followup_days = _days_since(contact, FOLLOWUP_FIELDS)
        if followup_days is None or followup_days > nurture_days:
            count += 1
    return count


def _count_missing_contact_channels(contacts: List[Dict[str, Any]]) -> int:
    count = 0
    for contact in contacts:
        email = contact.get('email')
        phone = contact.get('phone')
        if not email and not phone:
            count += 1
    return count


def _conversation_stale_days(conv: Dict[str, Any]) -> Optional[int]:
    return _days_since(conv, (
        'last_message_date', 'LAST_MESSAGE_DATE', 'lastMessageDate',
        'updatedAt', 'UPDATED_AT', 'dateUpdated',
    ))


def evaluate_compliance(
    datasets: Dict[str, Dict[str, List[Dict[str, Any]]]],
    connected: Dict[str, bool],
    inactive_days: int = 90,
    mask_contacts: bool = True,
) -> Dict[str, Any]:
    """
    Evaluate customer service data and recommend additional follow-ups.
    Includes HIPAA-oriented hygiene checks for medspa operations.
    """
    ghl = datasets.get('ghl') or {}
    snowflake = datasets.get('snowflake') or {}

    ghl_contacts = ghl.get('contacts') or []
    ghl_convs = ghl.get('conversations') or []
    ghl_opps = ghl.get('opportunities') or []
    sf_contacts = snowflake.get('contacts') or snowflake.get('ghl_contacts') or []
    sf_convs = snowflake.get('conversations') or snowflake.get('ghl_conversations') or []
    sf_opps = snowflake.get('opportunities') or snowflake.get('ghl_opportunities') or []

    all_contacts_raw = ghl_contacts + sf_contacts
    all_convs = ghl_convs + sf_convs
    all_opps = ghl_opps + sf_opps

    ghl_norm = [_normalize_contact(c, 'ghl') for c in ghl_contacts]
    sf_norm = [_normalize_contact(c, 'snowflake') for c in sf_contacts]
    inactive = [c for c in ghl_norm + sf_norm if _is_inactive_no_followup(c, inactive_days)]

    findings: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []
    deductions = 0

    if not connected.get('ghl') and not connected.get('snowflake'):
        return {
            'compliance_score': 0,
            'grade': 'N/A',
            'summary': 'Connect GoHighLevel and/or Snowflake to run a compliance evaluation.',
            'findings': [],
            'followup_recommendations': [],
            'evaluated_at': datetime.now(timezone.utc).isoformat(),
        }

    # Inactive patients
    if inactive:
        deductions += min(25, len(inactive) * 2)
        findings.append({
            'severity': 'high',
            'category': 'patient_followup',
            'title': 'Lapsed patients without follow-up',
            'detail': (
                f'{len(inactive)} patient(s) inactive ≥ {inactive_days} days with no documented follow-up.'
            ),
            'count': len(inactive),
        })
        for contact in inactive[:15]:
            recommendations.append(_rec(
                contact,
                priority='high',
                action='Send re-engagement email or call',
                reason=f'No activity or follow-up for {inactive_days}+ days (no-show risk)',
                channel='email',
                mask=mask_contacts,
            ))

    # Conversation backlog
    stale_convs = [c for c in all_convs if (_conversation_stale_days(c) or 0) >= 3]
    unread_total = sum(
        int(c.get('unreadCount') or c.get('unread_count') or c.get('UNREAD_COUNT') or 0)
        for c in all_convs
    )
    snoozed = [c for c in all_convs if str(c.get('status') or '').lower() == 'snoozed']

    if unread_total or snoozed or stale_convs:
        deductions += min(20, unread_total + len(snoozed) * 2 + len(stale_convs))
        findings.append({
            'severity': 'high' if unread_total else 'medium',
            'category': 'customer_service',
            'title': 'Patient messaging backlog',
            'detail': (
                f'{unread_total} unread, {len(snoozed)} snoozed, '
                f'{len(stale_convs)} thread(s) without a reply in 3+ days.'
            ),
            'count': unread_total + len(snoozed),
        })
        for conv in (snoozed + stale_convs)[:10]:
            contact_id = conv.get('contactId') or conv.get('contact_id') or conv.get('CONTACT_ID')
            recommendations.append({
                'priority': 'high' if conv in snoozed else 'medium',
                'action': 'Reply to patient thread and document next step',
                'reason': 'Snoozed or stale conversation hurts medspa response-time standards',
                'contact_id': str(contact_id or conv.get('id') or ''),
                'contact_name': 'Patient thread',
                'source': 'GoHighLevel' if conv in ghl_convs else 'Snowflake',
                'suggested_channel': 'sms',
                'conversation_id': str(conv.get('id') or conv.get('conversation_id') or ''),
            })

    # Missing contact channels
    missing = [c for c in ghl_norm + sf_norm if not c.get('email') and not c.get('phone')]
    if missing:
        deductions += min(15, len(missing) * 2)
        findings.append({
            'severity': 'medium',
            'category': 'data_quality',
            'title': 'Incomplete patient contact records',
            'detail': f'{len(missing)} record(s) missing both email and phone — limits HIPAA-safe outreach.',
            'count': len(missing),
        })
        for contact in missing[:8]:
            recommendations.append(_rec(
                contact,
                priority='medium',
                action='Update contact record with verified phone or email',
                reason='Cannot send compliant follow-up without a contact channel',
                channel='phone',
                mask=mask_contacts,
            ))

    # Stale open opportunities
    stale_opps = []
    for opp in all_opps:
        status = str(opp.get('status') or opp.get('STATUS') or '').lower()
        if status not in ('open', 'active', ''):
            continue
        if (_days_since(opp, DATE_FIELDS) or 0) >= 14:
            stale_opps.append(opp)
    if stale_opps:
        deductions += min(15, len(stale_opps) * 3)
        findings.append({
            'severity': 'medium',
            'category': 'pipeline',
            'title': 'Stalled treatment consults',
            'detail': f'{len(stale_opps)} open opportunity(ies) with no stage change in 14+ days.',
            'count': len(stale_opps),
        })
        for opp in stale_opps[:8]:
            name = opp.get('name') or opp.get('NAME') or 'Open consult'
            recommendations.append({
                'priority': 'medium',
                'action': 'Schedule consult follow-up call',
                'reason': 'Open pipeline deal stalled — revenue at risk',
                'contact_id': str(opp.get('contactId') or opp.get('contact_id') or ''),
                'contact_name': str(name),
                'source': 'GoHighLevel' if opp in ghl_opps else 'Snowflake',
                'suggested_channel': 'phone',
            })

    # New leads without nurture
    nurture_gap = _count_new_without_nurture(all_contacts_raw)
    if nurture_gap:
        deductions += min(12, nurture_gap * 2)
        findings.append({
            'severity': 'medium',
            'category': 'lead_nurture',
            'title': 'New leads missing 48-hour touch',
            'detail': f'{nurture_gap} lead(s) added in the last 30 days without a timely follow-up.',
            'count': nurture_gap,
        })

    # HIPAA hygiene (operational)
    findings.append({
        'severity': 'info',
        'category': 'hipaa_hygiene',
        'title': 'PHI masking active in query exports',
        'detail': 'Ensure all staff use masked views when sharing patient data externally.',
        'count': 0,
    })

    score = max(0, min(100, 100 - deductions))
    grade = 'A' if score >= 90 else 'B' if score >= 75 else 'C' if score >= 60 else 'D' if score >= 40 else 'F'

    # Sort recommendations by priority
    order = {'high': 0, 'medium': 1, 'low': 2}
    recommendations.sort(key=lambda r: order.get(r.get('priority', 'low'), 9))

    summary_parts = []
    if findings:
        high = sum(1 for f in findings if f['severity'] == 'high')
        summary_parts.append(f'{high} high-priority finding(s)')
    summary_parts.append(f'compliance score {score}/100')
    summary_parts.append(f'{len(recommendations)} follow-up recommendation(s)')

    return {
        'compliance_score': score,
        'grade': grade,
        'summary': '; '.join(summary_parts).capitalize() + '.',
        'findings': findings,
        'followup_recommendations': recommendations[:50],
        'recommendation_count': len(recommendations),
        'connected_sources': connected,
        'evaluated_at': datetime.now(timezone.utc).isoformat(),
    }


def _rec(
    contact: Dict[str, Any],
    *,
    priority: str,
    action: str,
    reason: str,
    channel: str,
    mask: bool,
) -> Dict[str, Any]:
    entry = {
        'priority': priority,
        'action': action,
        'reason': reason,
        'contact_id': contact.get('id') or '',
        'contact_name': contact.get('name') or 'Patient',
        'source': 'GoHighLevel' if contact.get('source') == 'ghl' else 'Snowflake',
        'suggested_channel': channel,
    }
    if mask:
        entry['contact_email'] = hipaa_manager_mask(contact.get('email'))
        entry['contact_phone'] = hipaa_manager_mask(contact.get('phone'))
    else:
        entry['contact_email'] = contact.get('email')
        entry['contact_phone'] = contact.get('phone')
    return entry
