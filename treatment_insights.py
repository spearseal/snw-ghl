"""
Patient treatment plans derived from Snowflake/GHL data and health intake forms.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from insights import (
    DATE_FIELDS,
    _contact_name,
    _days_since,
    _field,
    _normalize_contact,
    _sum_pipeline,
    hipaa_manager_mask,
)
from intake_store import get_intake_by_contact, list_intakes

TREATMENT_TAGS = {
    'botox': 'Neurotoxin (Botox/Dysport)',
    'dysport': 'Neurotoxin (Botox/Dysport)',
    'filler': 'Dermal fillers',
    'juvederm': 'Dermal fillers',
    'laser': 'Laser resurfacing',
    'ipl': 'IPL photofacial',
    'microneedling': 'Microneedling',
    'chemical peel': 'Chemical peel',
    'hydrafacial': 'HydraFacial',
    'coolsculpting': 'Body contouring',
    'prp': 'PRP therapy',
    'semaglutide': 'Weight management',
    'weight': 'Weight management',
}

INTAKE_FIELD_HINTS = (
    'skin', 'concern', 'allergy', 'allerg', 'medication', 'medical',
    'treatment', 'goal', 'intake', 'health', 'condition', 'budget',
)

STAGE_LABELS = {
    'consultation': 'Initial consultation',
    'active_treatment': 'Active treatment',
    'maintenance': 'Maintenance',
    're_engagement': 'Re-engagement',
}


def _record_tags(record: Dict[str, Any]) -> List[str]:
    tags = record.get('tags') or record.get('TAGS') or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    return [str(t).lower() for t in tags]


def _extract_intake_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Pull health/intake-like fields from flattened Snowflake/GHL columns."""
    found: Dict[str, Any] = {}
    for key, value in record.items():
        if value in (None, ''):
            continue
        key_lower = str(key).lower()
        if any(hint in key_lower for hint in INTAKE_FIELD_HINTS):
            found[key] = value
    return found


def _infer_services(tags: List[str], goals: str = '', concerns: str = '') -> List[str]:
    text = f"{' '.join(tags)} {goals} {concerns}".lower()
    services: List[str] = []
    for keyword, label in TREATMENT_TAGS.items():
        if keyword in text and label not in services:
            services.append(label)
    if not services:
        services.append('Comprehensive skin consult')
    return services[:5]


def _patient_opportunities(
    contact_id: str,
    opportunities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    matches = []
    for opp in opportunities:
        cid = str(
            opp.get('contactId') or opp.get('contact_id')
            or opp.get('CONTACT_ID') or ''
        )
        if cid and cid == str(contact_id):
            matches.append(opp)
    return matches


def _opp_value(opp: Dict[str, Any]) -> float:
    value = (
        opp.get('monetaryValue') or opp.get('monetary_value')
        or opp.get('MONETARY_VALUE') or opp.get('value') or 0
    )
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _determine_stage(
    contact: Dict[str, Any],
    opps: List[Dict[str, Any]],
    inactive_days: int,
) -> str:
    days_inactive = contact.get('days_inactive')
    open_opps = [
        o for o in opps
        if str(o.get('status') or o.get('STATUS') or 'open').lower() in ('open', 'active', '')
    ]
    won_opps = [
        o for o in opps
        if str(o.get('status') or o.get('STATUS') or '').lower() == 'won'
    ]

    if days_inactive is not None and days_inactive >= inactive_days:
        return 're_engagement'
    if open_opps:
        return 'active_treatment'
    if won_opps:
        return 'maintenance'
    return 'consultation'


def _build_plan_phases(
    stage: str,
    services: List[str],
    intake: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    goals = (intake or {}).get('treatment_goals', '')
    budget = (intake or {}).get('budget_range', '')

    if stage == 're_engagement':
        return [
            {
                'phase': 1,
                'title': 'Win-back outreach',
                'duration_weeks': 1,
                'services': ['Personalized check-in call', 'Complimentary skin assessment'],
                'priority': 'high',
                'notes': 'Patient has been inactive — prioritize reconnection before upsell.',
            },
            {
                'phase': 2,
                'title': 'Revised treatment roadmap',
                'duration_weeks': 4,
                'services': services[:2],
                'priority': 'medium',
                'notes': 'Align plan to updated goals after re-engagement consult.',
            },
        ]

    if stage == 'consultation':
        return [
            {
                'phase': 1,
                'title': 'Health intake review',
                'duration_weeks': 1,
                'services': ['Medical history review', 'Skin analysis'],
                'priority': 'high',
                'notes': 'Complete intake and flag allergies/contraindications.',
            },
            {
                'phase': 2,
                'title': 'Custom treatment design',
                'duration_weeks': 2,
                'services': services,
                'priority': 'high',
                'notes': f'Goals: {goals[:120] or "Define during consult"}'
                + (f' · Budget: {budget}' if budget else ''),
            },
            {
                'phase': 3,
                'title': 'Treatment kickoff',
                'duration_weeks': 4,
                'services': services[:2] or ['First treatment session'],
                'priority': 'medium',
                'notes': 'Book first procedure within 14 days of consult close.',
            },
        ]

    if stage == 'maintenance':
        return [
            {
                'phase': 1,
                'title': 'Maintenance cadence',
                'duration_weeks': 8,
                'services': services[:3] or ['Touch-up session'],
                'priority': 'medium',
                'notes': 'Schedule recurring visits based on prior treatment response.',
            },
            {
                'phase': 2,
                'title': 'Seasonal refresh',
                'duration_weeks': 12,
                'services': ['Skin health review', 'Add-on treatment evaluation'],
                'priority': 'low',
                'notes': 'Quarterly review to prevent lapse and identify upsell opportunities.',
            },
        ]

    # active_treatment
    return [
        {
            'phase': 1,
            'title': 'Active protocol — phase 1',
            'duration_weeks': 4,
            'services': services[:3],
            'priority': 'high',
            'notes': 'Execute open pipeline treatments; confirm pre-care instructions.',
        },
        {
            'phase': 2,
            'title': 'Active protocol — phase 2',
            'duration_weeks': 6,
            'services': services[1:4] or services,
            'priority': 'medium',
            'notes': 'Monitor results at 2-week checkpoint; adjust plan if needed.',
        },
        {
            'phase': 3,
            'title': 'Transition to maintenance',
            'duration_weeks': 8,
            'services': ['Results review', 'Maintenance scheduling'],
            'priority': 'medium',
            'notes': 'Close open opportunity and book follow-up before patient goes inactive.',
        },
    ]


def _risk_flags(intake: Optional[Dict[str, Any]], record: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    allergies = (intake or {}).get('allergies') or _field(record, ('allergies', 'ALLERGIES')) or ''
    meds = (intake or {}).get('current_medications') or _field(record, ('medications', 'MEDICATIONS')) or ''
    conditions = (intake or {}).get('medical_conditions') or _field(record, ('medical_conditions', 'MEDICAL_CONDITIONS')) or ''

    if allergies and str(allergies).strip().lower() not in ('none', 'n/a', 'no'):
        flags.append('Allergy reported — verify before procedure')
    if meds and str(meds).strip().lower() not in ('none', 'n/a', 'no'):
        flags.append('Medications on file — check contraindications')
    if conditions and str(conditions).strip().lower() not in ('none', 'n/a', 'no'):
        flags.append('Medical conditions noted — physician review recommended')
    return flags


def _build_patient_plan(
    record: Dict[str, Any],
    source: str,
    opportunities: List[Dict[str, Any]],
    intake: Optional[Dict[str, Any]],
    inactive_days: int,
    *,
    mask_phi: bool = True,
) -> Dict[str, Any]:
    contact = _normalize_contact(record, source)
    contact_id = contact['id']
    tags = _record_tags(record)
    embedded = _extract_intake_from_record(record)

    goals = (intake or {}).get('treatment_goals') or embedded.get('treatment_goals') or embedded.get('TREATMENT_GOALS') or ''
    concerns = (intake or {}).get('skin_concerns') or embedded.get('skin_concerns') or embedded.get('SKIN_CONCERNS') or ''
    services = _infer_services(tags, str(goals), str(concerns))

    patient_opps = _patient_opportunities(contact_id, opportunities)
    open_value = _sum_pipeline(patient_opps)
    stage = _determine_stage(contact, patient_opps, inactive_days)
    phases = _build_plan_phases(stage, services, intake)
    risks = _risk_flags(intake, record)

    intake_status = 'complete' if intake else ('partial' if embedded else 'none')

    plan = {
        'patient_id': contact_id,
        'patient_name': contact['name'],
        'source': source,
        'intake_status': intake_status,
        'current_stage': stage,
        'current_stage_label': STAGE_LABELS.get(stage, stage),
        'open_pipeline_value': round(open_value, 2),
        'open_opportunities': len([
            o for o in patient_opps
            if str(o.get('status') or o.get('STATUS') or 'open').lower() in ('open', 'active', '')
        ]),
        'recommended_services': services,
        'plan_phases': phases,
        'risk_flags': risks,
        'days_inactive': contact.get('days_inactive'),
        'next_action': _next_action(stage, intake_status, risks),
        'health_summary': {
            'skin_concerns': concerns or None,
            'treatment_goals': goals or None,
            'allergies': (intake or {}).get('allergies'),
            'budget_range': (intake or {}).get('budget_range'),
            'preferred_days': (intake or {}).get('preferred_days'),
            'embedded_fields': list(embedded.keys())[:8] if embedded else [],
        },
        'intake_id': (intake or {}).get('id'),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }

    if mask_phi:
        plan['patient_name'] = contact['name']  # name kept for display; mask email/phone if added
        if intake:
            plan['health_summary'] = {
                **plan['health_summary'],
                'allergies': hipaa_manager_mask((intake or {}).get('allergies')),
            }

    return plan


def _next_action(stage: str, intake_status: str, risks: List[str]) -> str:
    if risks:
        return 'Clinical review required before scheduling next procedure.'
    if intake_status == 'none':
        return 'Submit health intake form to personalize this treatment plan.'
    if stage == 're_engagement':
        return 'Send win-back message and offer complimentary skin consult within 7 days.'
    if stage == 'consultation':
        return 'Book initial consult and confirm intake details with patient.'
    if stage == 'active_treatment':
        return 'Confirm next treatment session and pre-care instructions.'
    return 'Schedule maintenance visit and capture progress photos.'


def compute_treatment_plans(
    datasets: Dict[str, Dict[str, List[Dict[str, Any]]]],
    connected: Dict[str, bool],
    inactive_days: int = 90,
    *,
    limit: int = 50,
    mask_phi: bool = True,
) -> Dict[str, Any]:
    snowflake = datasets.get('snowflake') or {}
    ghl = datasets.get('ghl') or {}

    sf_contacts = snowflake.get('contacts') or snowflake.get('ghl_contacts') or []
    sf_opps = snowflake.get('opportunities') or snowflake.get('ghl_opportunities') or []
    ghl_contacts = ghl.get('contacts') or []
    ghl_opps = ghl.get('opportunities') or []

    # Prefer Snowflake as primary source; fall back to GHL contacts
    primary_contacts: List[Tuple[Dict[str, Any], str]] = [
        (c, 'snowflake') for c in sf_contacts
    ]
    if not primary_contacts:
        primary_contacts = [(c, 'ghl') for c in ghl_contacts]

    all_opps = sf_opps + ghl_opps
    intakes = list_intakes(mask=False)
    intake_by_contact = {
        str(i.get('contact_id')): i for i in intakes if i.get('contact_id')
    }

    plans: List[Dict[str, Any]] = []
    for record, source in primary_contacts[:limit]:
        contact_id = str(
            record.get('id') or record.get('ID') or record.get('contactId') or ''
        )
        if not contact_id:
            continue
        intake = intake_by_contact.get(contact_id) or get_intake_by_contact(contact_id)
        plans.append(_build_patient_plan(
            record, source, all_opps, intake, inactive_days, mask_phi=mask_phi,
        ))

    # Plans for intake-only patients not yet in CRM
    seen_ids = {p['patient_id'] for p in plans}
    for intake in intakes:
        cid = str(intake.get('contact_id') or '')
        if cid and cid in seen_ids:
            continue
        pseudo_record = {
            'id': cid or intake.get('id'),
            'firstName': intake.get('patient_name', '').split(' ')[0],
            'lastName': ' '.join(intake.get('patient_name', '').split(' ')[1:]),
            'email': intake.get('email'),
            'phone': intake.get('phone'),
            'tags': [],
        }
        plans.append(_build_patient_plan(
            pseudo_record,
            'intake',
            all_opps,
            intake,
            inactive_days,
            mask_phi=mask_phi,
        ))

    plans.sort(key=lambda p: (
        0 if p['intake_status'] == 'none' else 1,
        -(p.get('open_pipeline_value') or 0),
        p.get('days_inactive') or 0,
    ))

    pending_intake = sum(1 for p in plans if p['intake_status'] == 'none')
    active = sum(1 for p in plans if p['current_stage'] == 'active_treatment')
    reengage = sum(1 for p in plans if p['current_stage'] == 're_engagement')

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'connected_sources': connected,
        'summary': {
            'total_patients': len(plans),
            'pending_intake': pending_intake,
            'active_treatment': active,
            're_engagement': reengage,
            'intakes_on_file': len(intakes),
        },
        'plans': plans,
        'message': (
            None if plans else
            'No patient records found. Connect Snowflake and sync ghl_contacts, or submit a health intake form.'
        ),
    }


def compute_plan_for_intake(intake: Dict[str, Any], datasets: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a treatment plan immediately after intake submission."""
    snowflake = datasets.get('snowflake') or {}
    ghl = datasets.get('ghl') or {}
    sf_contacts = snowflake.get('contacts') or snowflake.get('ghl_contacts') or []
    ghl_contacts = ghl.get('contacts') or []
    all_opps = (
        (snowflake.get('opportunities') or snowflake.get('ghl_opportunities') or [])
        + (ghl.get('opportunities') or [])
    )

    contact_id = str(intake.get('contact_id') or '')
    record = None
    source = 'intake'
    for c in sf_contacts:
        if str(c.get('id') or c.get('ID') or '') == contact_id:
            record, source = c, 'snowflake'
            break
    if not record:
        for c in ghl_contacts:
            if str(c.get('id') or c.get('ID') or '') == contact_id:
                record, source = c, 'ghl'
                break

    if not record:
        record = {
            'id': contact_id or intake.get('id'),
            'firstName': intake.get('patient_name', '').split(' ')[0],
            'lastName': ' '.join(intake.get('patient_name', '').split(' ')[1:]),
            'email': intake.get('email'),
            'phone': intake.get('phone'),
        }

    return _build_patient_plan(record, source, all_opps, intake, inactive_days=90, mask_phi=True)
