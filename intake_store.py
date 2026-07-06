"""
Health intake form storage (encrypted PHI) for treatment plan generation.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from hipaa_compliance import hipaa_manager

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get(
    'DATA_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
)
INTAKE_FILE = os.path.join(DATA_DIR, 'health_intakes.json')

PHI_FIELDS = {
    'patient_name', 'email', 'phone', 'date_of_birth',
    'skin_concerns', 'allergies', 'current_medications',
    'medical_conditions', 'treatment_goals',
}


class HealthIntakeForm(BaseModel):
    patient_name: str = Field(min_length=1, max_length=200)
    email: str = Field(default='', max_length=254)
    phone: str = Field(default='', max_length=50)
    contact_id: str = Field(default='', max_length=100)
    date_of_birth: str = Field(default='', max_length=20)
    skin_concerns: str = Field(default='', max_length=2000)
    allergies: str = Field(default='', max_length=1000)
    current_medications: str = Field(default='', max_length=1000)
    treatment_goals: str = Field(default='', max_length=2000)
    budget_range: str = Field(default='', max_length=50)
    preferred_days: str = Field(default='', max_length=200)
    medical_conditions: str = Field(default='', max_length=1000)
    consent_acknowledged: bool = False


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _encrypt_phi(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    for key in PHI_FIELDS:
        if out.get(key):
            out[key] = hipaa_manager.encrypt_data(str(out[key]))
    return out


def _decrypt_phi(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    for key in PHI_FIELDS:
        if out.get(key):
            try:
                out[key] = hipaa_manager.decrypt_data(out[key])
            except Exception:
                pass
    return out


def _mask_phi(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    for key in ('email', 'phone', 'date_of_birth'):
        if out.get(key):
            out[key] = hipaa_manager.mask_sensitive_data(str(out[key]))
    return out


def _load_all() -> List[Dict[str, Any]]:
    _ensure_data_dir()
    if not os.path.exists(INTAKE_FILE):
        return []
    try:
        with open(INTAKE_FILE, 'r', encoding='utf-8') as f:
            records = json.load(f)
        return [_decrypt_phi(r) for r in records if isinstance(r, dict)]
    except Exception as e:
        logger.error('Failed to load intakes: %s', e)
        return []


def _save_all(records: List[Dict[str, Any]]) -> None:
    _ensure_data_dir()
    encrypted = [_encrypt_phi(r) for r in records]
    with open(INTAKE_FILE, 'w', encoding='utf-8') as f:
        json.dump(encrypted, f, indent=2)


def save_intake(form: HealthIntakeForm) -> Dict[str, Any]:
    if not form.consent_acknowledged:
        raise ValueError('Patient consent is required before submitting intake.')

    record = form.model_dump()
    record['id'] = str(uuid.uuid4())
    record['submitted_at'] = datetime.now(timezone.utc).isoformat()

    records = _load_all()
    records.append(record)
    _save_all(records)

    hipaa_manager.log_audit_event('intake_submitted', {
        'intake_id': record['id'],
        'contact_id': record.get('contact_id') or None,
        'timestamp': record['submitted_at'],
    })
    return record


def list_intakes(*, mask: bool = True) -> List[Dict[str, Any]]:
    records = _load_all()
    if mask:
        return [_mask_phi(r) for r in records]
    return records


def get_intake_by_contact(contact_id: str) -> Optional[Dict[str, Any]]:
    if not contact_id:
        return None
    for record in reversed(_load_all()):
        if str(record.get('contact_id') or '') == str(contact_id):
            return record
    return None


def get_intake_by_id(intake_id: str) -> Optional[Dict[str, Any]]:
    for record in _load_all():
        if record.get('id') == intake_id:
            return record
    return None
