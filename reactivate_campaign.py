"""
Reactivate campaign: identify 90+ day no-show patients, offer discounts,
email outreach or manual follow-up lists.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from email_followup import (
    _send_via_smtp,
    load_email_settings,
    save_email_settings,
)
from hipaa_compliance import hipaa_manager
from insights import compute_insights, hipaa_manager_mask

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get(
    'DATA_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
)
REACTIVATE_SETTINGS_FILE = os.path.join(DATA_DIR, 'reactivate_settings.json')

DEFAULT_SUBJECT = "We miss you, {{first_name}} — {{discount}} on your next visit"
DEFAULT_BODY = """<p>Hi {{name}},</p>
<p>It's been a while since your last visit and we'd love to welcome you back.</p>
<p>As a valued patient, enjoy <strong>{{discount}}</strong> on your next treatment when you book by the end of this month.</p>
<p>Use code <strong>{{discount_code}}</strong> at checkout or mention it when you call.</p>
<p>Reply to this email or call us at your convenience — we have appointment slots ready for you.</p>
<p>Warm regards,<br/>Your medspa team</p>"""


class ReactivateSettings(BaseModel):
    inactive_days: int = Field(default=90, ge=30, le=365)
    discount_percent: int = Field(default=15, ge=5, le=50)
    discount_code: str = Field(default='COMEBACK15', max_length=32)
    discount_label: str = Field(default='15% off your next visit', max_length=120)
    subject_template: str = Field(default=DEFAULT_SUBJECT, max_length=500)
    body_template: str = Field(default=DEFAULT_BODY, max_length=10000)
    provider: str = Field(default='ghl', description='ghl or smtp')
    enabled: bool = True


class ReactivateSendRequest(BaseModel):
    contact_ids: Optional[List[str]] = None
    send_all: bool = False
    dry_run: bool = False
    channel: str = Field(default='email', description='email only for send endpoint')


def _default_settings() -> Dict[str, Any]:
    return ReactivateSettings().model_dump()


def load_reactivate_settings() -> Dict[str, Any]:
    if not os.path.exists(REACTIVATE_SETTINGS_FILE):
        return _default_settings()
    with open(REACTIVATE_SETTINGS_FILE, 'r', encoding='utf-8') as f:
        stored = json.load(f)
    return {**_default_settings(), **stored}


def save_reactivate_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    current = load_reactivate_settings()
    for key, value in payload.items():
        if value is not None:
            current[key] = value
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REACTIVATE_SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(current, f, indent=2)
    hipaa_manager.log_audit_event('reactivate_settings_updated', {
        'discount_percent': current.get('discount_percent'),
        'discount_code': current.get('discount_code'),
        'inactive_days': current.get('inactive_days'),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })
    return current


def render_campaign_template(template: str, contact: Dict[str, Any], settings: Dict[str, Any]) -> str:
    name = contact.get('name') or 'there'
    first = name.split()[0] if name and name != 'Unknown' else 'there'
    discount_label = settings.get('discount_label') or f"{settings.get('discount_percent', 15)}% off"
    replacements = {
        '{{name}}': name,
        '{{first_name}}': first,
        '{{email}}': contact.get('email') or '',
        '{{phone}}': contact.get('phone') or '',
        '{{source}}': contact.get('source') or '',
        '{{discount}}': discount_label,
        '{{discount_code}}': settings.get('discount_code') or 'COMEBACK15',
        '{{discount_percent}}': str(settings.get('discount_percent', 15)),
        '{{days_inactive}}': str(contact.get('days_inactive') or ''),
    }
    result = template
    for token, value in replacements.items():
        result = result.replace(token, str(value))
    return result


def _discount_offer(settings: Dict[str, Any]) -> str:
    label = settings.get('discount_label') or ''
    code = settings.get('discount_code') or ''
    pct = settings.get('discount_percent', 15)
    if label:
        return f'{label} (code: {code})' if code else label
    return f'{pct}% off (code: {code})'


def _manual_script(contact: Dict[str, Any], settings: Dict[str, Any]) -> str:
    name = contact.get('name') or 'patient'
    first = name.split()[0] if name else 'there'
    offer = _discount_offer(settings)
    days = contact.get('days_inactive') or '90+'
    return (
        f"Hi {first}, this is [your name] from the medspa. We noticed it's been "
        f"about {days} days since your last visit. We'd love to welcome you back "
        f"with {offer}. Can I book a convenient time for you this week?"
    )


def _segment_candidates(
    candidates: List[Dict[str, Any]],
    settings: Dict[str, Any],
    *,
    mask_phi: bool = True,
) -> Dict[str, Any]:
    email_ready: List[Dict[str, Any]] = []
    manual_only: List[Dict[str, Any]] = []
    offer = _discount_offer(settings)

    for contact in candidates:
        entry = {
            'id': contact.get('id') or '',
            'name': contact.get('name') or 'Unknown',
            'email': contact.get('email'),
            'phone': contact.get('phone'),
            'source': contact.get('source') or '',
            'days_inactive': contact.get('days_inactive'),
            'days_since_followup': contact.get('days_since_followup'),
            'discount_offer': offer,
            'discount_code': settings.get('discount_code'),
            'discount_percent': settings.get('discount_percent'),
        }

        if mask_phi:
            entry['email'] = hipaa_manager_mask(entry.get('email'))
            entry['phone'] = hipaa_manager_mask(entry.get('phone'))

        has_email = bool(contact.get('email') and '@' in str(contact['email']))
        has_phone = bool(contact.get('phone'))

        if has_email:
            entry['channel'] = 'email'
            email_ready.append(entry)
        elif has_phone:
            entry['channel'] = 'manual'
            entry['call_script'] = _manual_script(contact if not mask_phi else {
                **contact,
                'name': entry['name'],
            }, settings)
            manual_only.append(entry)
        else:
            entry['channel'] = 'manual'
            entry['call_script'] = _manual_script(contact if not mask_phi else {
                **contact,
                'name': entry['name'],
            }, settings)
            manual_only.append(entry)

    return {
        'email_ready': email_ready,
        'manual_only': manual_only,
        'total': len(candidates),
    }


def compute_reactivate_campaign(
    datasets: Dict[str, Any],
    connected: Dict[str, bool],
    *,
    inactive_days: Optional[int] = None,
    mask_phi: bool = True,
    page: int = 1,
    page_size: int = 25,
    q: str = '',
    channel: str = 'all',
    sort: str = '-days_inactive',
) -> Dict[str, Any]:
    settings = load_reactivate_settings()
    threshold = inactive_days if inactive_days is not None else settings.get('inactive_days', 90)

    insights = compute_insights(
        datasets, connected, inactive_days=threshold, mask_contacts=mask_phi,
    )
    raw_candidates = insights.get('followup_candidates') or []

    if not mask_phi:
        # Re-fetch unmasked for internal send/export
        insights_raw = compute_insights(
            datasets, connected, inactive_days=threshold, mask_contacts=False,
        )
        raw_candidates = insights_raw.get('followup_candidates') or []

    segmented = _segment_candidates(raw_candidates, settings, mask_phi=mask_phi)

    def _filter_sort(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filtered = items
        if q.strip():
            needle = q.strip().lower()
            filtered = [
                c for c in filtered
                if needle in (c.get('name') or '').lower()
                or needle in str(c.get('email') or '').lower()
                or needle in str(c.get('phone') or '').lower()
                or needle in str(c.get('source') or '').lower()
            ]
        reverse = sort.startswith('-')
        field = sort.lstrip('-') or 'days_inactive'
        if field in ('days_inactive', 'name', 'source'):
            filtered = sorted(
                filtered,
                key=lambda c: (c.get(field) is None, c.get(field) or ''),
                reverse=reverse,
            )
        return filtered

    email_all = _filter_sort(segmented['email_ready'])
    manual_all = _filter_sort(segmented['manual_only'])

    def _page(items: List[Dict[str, Any]], p: int, size: int) -> Dict[str, Any]:
        total = len(items)
        total_pages = max(1, (total + size - 1) // size) if total else 1
        safe_page = min(max(1, p), total_pages)
        start = (safe_page - 1) * size
        return {
            'items': items[start:start + size],
            'meta': {
                'page': safe_page,
                'page_size': size,
                'total': total,
                'total_pages': total_pages,
                'has_next': safe_page < total_pages,
                'has_prev': safe_page > 1,
            },
        }

    email_paged = _page(email_all, page if channel in ('all', 'email') else 1, page_size)
    manual_paged = _page(manual_all, page if channel in ('all', 'manual') else 1, page_size)

    if channel == 'email':
        list_pagination = email_paged['meta']
    elif channel == 'manual':
        list_pagination = manual_paged['meta']
    else:
        list_pagination = _page(email_all + manual_all, page, page_size)['meta']

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'connected_sources': connected,
        'inactive_days_threshold': threshold,
        'settings': {
            'inactive_days': threshold,
            'discount_percent': settings.get('discount_percent'),
            'discount_code': settings.get('discount_code'),
            'discount_label': settings.get('discount_label'),
            'subject_template': settings.get('subject_template'),
            'body_template': settings.get('body_template'),
            'provider': settings.get('provider'),
            'enabled': settings.get('enabled'),
        },
        'summary': {
            'total_candidates': segmented['total'],
            'email_ready': len(email_all),
            'manual_followup': len(manual_all),
            'discount_offer': _discount_offer(settings),
        },
        'candidates': {
            'email_ready': email_paged['items'],
            'manual_only': manual_paged['items'],
            'total': segmented['total'],
        },
        'pagination': list_pagination,
        'filters': {'q': q, 'channel': channel, 'sort': sort},
        'errors': None,
        'message': (
            None if segmented['total'] else
            f'No patients found with {threshold}+ days no show and no follow-up. '
            'Connect data sources and refresh.'
        ),
    }


def send_reactivate_emails(
    candidates: List[Dict[str, Any]],
    *,
    contact_ids: Optional[List[str]] = None,
    send_all: bool = False,
    dry_run: bool = False,
    ghl_client: Any = None,
) -> Dict[str, Any]:
    settings = load_reactivate_settings()
    if not settings.get('enabled'):
        raise ValueError('Reactivate campaign is disabled')

    email_cfg = load_email_settings()
    provider = (settings.get('provider') or email_cfg.get('provider') or 'ghl').lower()

    selected = candidates
    if contact_ids and not send_all:
        id_set = set(contact_ids)
        selected = [c for c in candidates if c.get('id') in id_set]

    with_email = [c for c in selected if c.get('email') and '@' in str(c['email'])]
    if not with_email:
        return {
            'status': 'ok',
            'sent': 0,
            'skipped': len(selected),
            'errors': [],
            'dry_run': dry_run,
            'message': 'No email-ready candidates in selection',
        }

    sent = 0
    errors: List[Dict[str, str]] = []

    for contact in with_email:
        subject = render_campaign_template(settings['subject_template'], contact, settings)
        body = render_campaign_template(settings['body_template'], contact, settings)
        to_email = contact['email']

        if dry_run:
            sent += 1
            continue

        try:
            if provider == 'ghl':
                if not ghl_client:
                    raise ValueError('GoHighLevel is not connected')
                ghl_client.send_email(
                    contact_id=contact['id'],
                    subject=subject,
                    html=body,
                    from_email=email_cfg.get('from_email') or None,
                )
            else:
                _send_via_smtp(email_cfg, to_email, subject, body)
            sent += 1
        except Exception as e:
            logger.error('Reactivate email failed for %s: %s', contact.get('id'), e)
            errors.append({'contact_id': contact.get('id') or '', 'error': str(e)})

    hipaa_manager.log_audit_event('reactivate_campaign_sent', {
        'sent': sent,
        'errors': len(errors),
        'provider': provider,
        'dry_run': dry_run,
        'discount_code': settings.get('discount_code'),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })

    return {
        'status': 'ok',
        'sent': sent,
        'skipped': len(selected) - len(with_email),
        'errors': errors,
        'dry_run': dry_run,
        'provider': provider,
        'discount_code': settings.get('discount_code'),
    }


def export_manual_followup_csv(candidates: List[Dict[str, Any]], settings: Dict[str, Any]) -> str:
    """CSV for staff manual phone follow-up."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Name', 'Phone', 'Email', 'Source', 'Days Inactive',
        'Discount Offer', 'Discount Code', 'Suggested Call Script',
    ])
    offer = _discount_offer(settings)
    code = settings.get('discount_code', '')

    for contact in candidates:
        has_email = bool(contact.get('email') and '@' in str(contact['email']))
        if has_email:
            continue
        writer.writerow([
            contact.get('name') or '',
            contact.get('phone') or '',
            contact.get('email') or '',
            contact.get('source') or '',
            contact.get('days_inactive') or '',
            offer,
            code,
            _manual_script(contact, settings),
        ])

    return output.getvalue()


def export_all_followup_csv(candidates: List[Dict[str, Any]], settings: Dict[str, Any]) -> str:
    """Full export including email-ready for CRM import."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Name', 'Phone', 'Email', 'Source', 'Days Inactive', 'Channel',
        'Discount Offer', 'Discount Code', 'Suggested Call Script',
    ])
    offer = _discount_offer(settings)
    code = settings.get('discount_code', '')

    for contact in candidates:
        has_email = bool(contact.get('email') and '@' in str(contact['email']))
        channel = 'email' if has_email else 'manual'
        writer.writerow([
            contact.get('name') or '',
            contact.get('phone') or '',
            contact.get('email') or '',
            contact.get('source') or '',
            contact.get('days_inactive') or '',
            channel,
            offer,
            code,
            _manual_script(contact, settings) if channel == 'manual' else '',
        ])

    return output.getvalue()
