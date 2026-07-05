"""
Email follow-up settings and campaign sending for inactive customers.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import settings
from hipaa_compliance import hipaa_manager

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get(
    'DATA_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
)
EMAIL_SETTINGS_FILE = os.path.join(DATA_DIR, 'email_settings.json')

SECRET_FIELDS = {'smtp_password'}
DEFAULT_SUBJECT = "We'd love to reconnect — {{name}}"
DEFAULT_BODY = """<p>Hi {{name}},</p>
<p>We noticed it has been a while since we last connected. We'd love to help you with your next step.</p>
<p>Reply to this email or call us anytime — we're here for you.</p>
<p>Best regards,<br/>Your team</p>"""


class EmailSettings(BaseModel):
    provider: str = Field(default='ghl', description='ghl or smtp')
    inactive_days: int = Field(default=90, ge=30, le=365)
    subject_template: str = Field(default=DEFAULT_SUBJECT, max_length=500)
    body_template: str = Field(default=DEFAULT_BODY, max_length=10000)
    from_email: str = Field(default='', max_length=254)
    from_name: str = Field(default='Your Team', max_length=100)
    smtp_host: str = Field(default='', max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = Field(default='', max_length=255)
    smtp_password: str = Field(default='', max_length=500)
    smtp_use_tls: bool = True
    enabled: bool = True


class SendFollowupRequest(BaseModel):
    contact_ids: Optional[List[str]] = None
    send_all: bool = False
    dry_run: bool = False


def _default_settings() -> Dict[str, Any]:
    return EmailSettings().model_dump()


def _encrypt_secrets(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    for key in SECRET_FIELDS:
        if out.get(key):
            out[key] = hipaa_manager.encrypt_data(out[key])
    return out


def _decrypt_secrets(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    for key in SECRET_FIELDS:
        if out.get(key):
            try:
                out[key] = hipaa_manager.decrypt_data(out[key])
            except Exception:
                pass
    return out


def _public_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    if out.get('smtp_password'):
        out['smtp_password'] = '••••••••'
    return out


def load_email_settings() -> Dict[str, Any]:
    if not os.path.exists(EMAIL_SETTINGS_FILE):
        return _default_settings()
    with open(EMAIL_SETTINGS_FILE, 'r') as f:
        stored = json.load(f)
    merged = {**_default_settings(), **stored}
    return _decrypt_secrets(merged)


def save_email_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    current = load_email_settings()
    for key, value in payload.items():
        if key in SECRET_FIELDS and (not value or value == '••••••••'):
            continue
        current[key] = value
    os.makedirs(DATA_DIR, exist_ok=True)
    to_store = _encrypt_secrets(current)
    with open(EMAIL_SETTINGS_FILE, 'w') as f:
        json.dump(to_store, f, indent=2)
    hipaa_manager.log_audit_event('email_settings_updated', {
        'provider': current.get('provider'),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })
    return _public_settings(current)


def render_template(template: str, contact: Dict[str, Any]) -> str:
    name = contact.get('name') or 'there'
    replacements = {
        '{{name}}': name,
        '{{first_name}}': name.split()[0] if name else 'there',
        '{{email}}': contact.get('email') or '',
        '{{phone}}': contact.get('phone') or '',
        '{{source}}': contact.get('source') or '',
    }
    result = template
    for token, value in replacements.items():
        result = result.replace(token, str(value))
    return result


def _send_via_smtp(
    settings_data: Dict[str, Any],
    to_email: str,
    subject: str,
    html_body: str,
) -> None:
    host = settings_data.get('smtp_host') or settings.smtp_host
    port = int(settings_data.get('smtp_port') or settings.smtp_port or 587)
    user = settings_data.get('smtp_user') or settings.smtp_user
    password = settings_data.get('smtp_password') or settings.smtp_password
    from_email = settings_data.get('from_email') or settings.email_from or user
    use_tls = settings_data.get('smtp_use_tls', True)

    if not host or not user or not password:
        raise ValueError('SMTP host, user, and password are required for SMTP provider')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    msg.attach(MIMEText(html_body, 'html'))

    with smtplib.SMTP(host, port, timeout=30) as server:
        if use_tls:
            server.starttls()
        server.login(user, password)
        server.sendmail(from_email, [to_email], msg.as_string())


def send_followup_emails(
    candidates: List[Dict[str, Any]],
    *,
    contact_ids: Optional[List[str]] = None,
    send_all: bool = False,
    dry_run: bool = False,
    ghl_client: Any = None,
) -> Dict[str, Any]:
    """Send re-engagement emails to inactive contacts via GHL or SMTP."""
    settings_data = load_email_settings()
    if not settings_data.get('enabled'):
        raise ValueError('Email follow-up is disabled in settings')

    provider = (settings_data.get('provider') or 'ghl').lower()
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
            'message': 'No candidates with email addresses found',
        }

    sent = 0
    errors: List[Dict[str, str]] = []

    for contact in with_email:
        subject = render_template(settings_data['subject_template'], contact)
        body = render_template(settings_data['body_template'], contact)
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
                    from_email=settings_data.get('from_email') or None,
                )
            else:
                _send_via_smtp(settings_data, to_email, subject, body)
            sent += 1
        except Exception as e:
            logger.error(f"Follow-up email failed for {contact.get('id')}: {e}")
            errors.append({
                'contact_id': contact.get('id') or '',
                'error': str(e),
            })

    hipaa_manager.log_audit_event('email_followup_sent', {
        'sent': sent,
        'errors': len(errors),
        'provider': provider,
        'dry_run': dry_run,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })

    return {
        'status': 'ok',
        'sent': sent,
        'skipped': len(selected) - len(with_email),
        'errors': errors,
        'dry_run': dry_run,
        'provider': provider,
    }
