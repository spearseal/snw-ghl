"""
Aggregated business reports from connected GHL + Snowflake data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from insights import compute_insights
from medspa_insights import compute_ceo_tasks, evaluate_compliance
from reactivate_campaign import compute_reactivate_campaign, load_reactivate_settings
from revenue_insights import compute_revenue_growth
from treatment_insights import compute_treatment_plans


def _metric(label: str, value: Any, detail: str = '') -> Dict[str, Any]:
    return {'label': label, 'value': value, 'detail': detail}


def compute_reports(
    datasets: Dict[str, Any],
    connected: Dict[str, bool],
    *,
    inactive_days: int = 90,
) -> Dict[str, Any]:
    insights = compute_insights(datasets, connected, inactive_days=inactive_days, mask_contacts=True)
    revenue = compute_revenue_growth(datasets, connected, months=12, inactive_days=inactive_days)
    compliance = evaluate_compliance(datasets, connected, inactive_days=inactive_days, mask_contacts=True)
    treatment = compute_treatment_plans(datasets, connected, inactive_days=inactive_days, limit=100, mask_phi=True)
    reactivate = compute_reactivate_campaign(
        datasets, connected, inactive_days=inactive_days, mask_phi=True,
        page=1, page_size=100,
    )
    ceo_tasks = compute_ceo_tasks(datasets, connected, inactive_days=inactive_days)

    summary = insights.get('summary') or {}
    rev_summary = revenue.get('summary') or {}
    treat_summary = treatment.get('summary') or {}
    react_summary = reactivate.get('summary') or {}

    ghl = summary.get('ghl') or {}
    sf = summary.get('snowflake') or {}

    reports: List[Dict[str, Any]] = [
        {
            'id': 'executive',
            'title': 'Executive Summary',
            'description': 'Cross-source KPIs and audience reach',
            'category': 'operations',
            'metrics': [
                _metric('Total contacts', (ghl.get('contacts') or 0) + (sf.get('contacts') or 0)),
                _metric('Open pipeline', rev_summary.get('current_open_pipeline', 0), 'USD'),
                _metric('Re-engagement queue', insights.get('followup_candidate_count', 0)),
                _metric('Compliance score', compliance.get('compliance_score', 'N/A')),
            ],
            'highlights': [
                f"GHL: {ghl.get('contacts', 0)} contacts, {ghl.get('opportunities', 0)} opportunities",
                f"Snowflake: {sf.get('contacts', 0)} contacts, {sf.get('opportunities', 0)} opportunities",
                f"{len(ceo_tasks)} CEO priority tasks generated",
            ],
        },
        {
            'id': 'revenue',
            'title': 'Revenue & Pipeline',
            'description': 'Monthly won revenue, pipeline, and decision factors',
            'category': 'finance',
            'metrics': [
                _metric('YTD won revenue', f"${rev_summary.get('ytd_won_revenue', 0):,.0f}"),
                _metric('Open pipeline', f"${rev_summary.get('current_open_pipeline', 0):,.0f}"),
                _metric('Open deals', rev_summary.get('current_open_deals', 0)),
                _metric('YTD new leads', rev_summary.get('ytd_new_contacts', 0)),
            ],
            'rows': [
                {
                    'month': m.get('month'),
                    'won_revenue': m.get('won_revenue'),
                    'new_contacts': m.get('new_contacts'),
                    'won_count': m.get('won_count'),
                    'lost_count': m.get('lost_count'),
                    'stale_opportunities': m.get('stale_opportunities'),
                }
                for m in (revenue.get('monthly') or [])[-6:]
            ],
        },
        {
            'id': 'retention',
            'title': 'Patient Retention & Reactivation',
            'description': f'Patients inactive ≥ {inactive_days} days with no follow-up',
            'category': 'clinical',
            'metrics': [
                _metric('At-risk patients', react_summary.get('total_candidates', 0)),
                _metric('Email-ready', react_summary.get('email_ready', 0)),
                _metric('Manual follow-up', react_summary.get('manual_followup', 0)),
                _metric('GHL inactive', ghl.get('inactive_no_followup', 0)),
            ],
            'rows': [
                {
                    'name': c.get('name'),
                    'source': c.get('source'),
                    'days_inactive': c.get('days_inactive'),
                    'channel': 'email',
                }
                for c in (reactivate.get('candidates') or {}).get('email_ready', [])[:10]
            ],
        },
        {
            'id': 'treatment',
            'title': 'Treatment Plans',
            'description': 'Patient care stages and intake status',
            'category': 'clinical',
            'metrics': [
                _metric('Total patients', treat_summary.get('total_patients', 0)),
                _metric('Pending intake', treat_summary.get('pending_intake', 0)),
                _metric('Active treatment', treat_summary.get('active_treatment', 0)),
                _metric('Re-engagement', treat_summary.get('re_engagement', 0)),
            ],
            'rows': [
                {
                    'patient': p.get('patient_name'),
                    'stage': p.get('current_stage_label'),
                    'intake': p.get('intake_status'),
                    'pipeline': p.get('open_pipeline_value'),
                }
                for p in (treatment.get('plans') or [])[:10]
            ],
        },
        {
            'id': 'compliance',
            'title': 'Compliance & Service Quality',
            'description': 'HIPAA-oriented service evaluation and follow-up gaps',
            'category': 'compliance',
            'metrics': [
                _metric('Compliance score', compliance.get('compliance_score', 0)),
                _metric('Grade', compliance.get('grade', 'N/A')),
                _metric('Findings', len(compliance.get('findings') or [])),
                _metric('Follow-up actions', compliance.get('recommendation_count', 0)),
            ],
            'highlights': [
                compliance.get('summary') or 'No summary available.',
            ],
            'rows': [
                {
                    'title': f.get('title'),
                    'severity': f.get('severity'),
                    'count': f.get('count'),
                }
                for f in (compliance.get('findings') or [])[:10]
            ],
        },
        {
            'id': 'ceo',
            'title': 'CEO Priority Tasks',
            'description': 'Top 5 medspa CEO actions from live data',
            'category': 'leadership',
            'metrics': [
                _metric('Tasks generated', len(ceo_tasks)),
                _metric('High priority', sum(1 for t in ceo_tasks if t.get('priority') == 'high')),
            ],
            'rows': [
                {
                    'rank': t.get('rank'),
                    'title': t.get('title'),
                    'priority': t.get('priority'),
                    'metric': t.get('metric'),
                    'category': t.get('category'),
                }
                for t in ceo_tasks
            ],
        },
    ]

    sources = []
    if connected.get('ghl'):
        sources.append('GoHighLevel')
    if connected.get('snowflake'):
        sources.append('Snowflake')

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'connected_sources': connected,
        'source_label': ' + '.join(sources) if sources else 'No source connected',
        'inactive_days_threshold': inactive_days,
        'reports': reports,
        'message': (
            None if connected.get('ghl') or connected.get('snowflake') else
            'Connect data sources to generate reports.'
        ),
    }


def report_to_csv_rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten a report section for CSV/Excel export."""
    rows = report.get('rows') or []
    if rows:
        return rows
    return [
        {'label': m['label'], 'value': m['value'], 'detail': m.get('detail', '')}
        for m in report.get('metrics') or []
    ]
