"""
DB connector management.
Stores Snowflake / GoHighLevel connection configs in data/connections.json
with secrets encrypted via the HIPAA compliance manager, and supports
live connection testing.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

import requests
import snowflake.connector
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from config import settings
from hipaa_compliance import hipaa_manager

DATA_DIR = os.environ.get(
    'DATA_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
)
CONNECTIONS_FILE = os.path.join(DATA_DIR, 'connections.json')

SECRET_FIELDS = {'password', 'api_key', 'passcode'}

router = APIRouter(prefix='/api/connections', tags=['connections'])


class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: Literal['snowflake', 'ghl']
    config: Dict[str, str]


def _load_connections() -> List[Dict[str, Any]]:
    if not os.path.exists(CONNECTIONS_FILE):
        return []
    with open(CONNECTIONS_FILE, 'r') as f:
        return json.load(f)


def _save_connections(connections: List[Dict[str, Any]]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONNECTIONS_FILE, 'w') as f:
        json.dump(connections, f, indent=2)


def _encrypt_config(config: Dict[str, str]) -> Dict[str, str]:
    return {
        k: hipaa_manager.encrypt_data(v) if k in SECRET_FIELDS and v else v
        for k, v in config.items()
    }


def _decrypt_config(config: Dict[str, str]) -> Dict[str, str]:
    out = {}
    for k, v in config.items():
        if k in SECRET_FIELDS and v:
            try:
                out[k] = hipaa_manager.decrypt_data(v)
            except Exception:
                out[k] = v
        else:
            out[k] = v
    return out


def _public_view(conn: Dict[str, Any]) -> Dict[str, Any]:
    """Return a connection with secret fields masked"""
    view = {k: v for k, v in conn.items() if k != 'config'}
    view['config'] = {
        k: ('••••••••' if k in SECRET_FIELDS and v else v)
        for k, v in conn['config'].items()
    }
    return view


def _seed_defaults():
    """Seed default Snowflake and GHL connections from the .env config"""
    connections = _load_connections()
    existing_types = {c['type'] for c in connections if c.get('is_default')}
    changed = False

    if 'snowflake' not in existing_types and settings.snowflake_account:
        connections.append({
            'id': str(uuid.uuid4()),
            'name': 'Default Snowflake (.env)',
            'type': 'snowflake',
            'is_default': True,
            'config': _encrypt_config({
                'account': settings.snowflake_account,
                'user': settings.snowflake_user,
                'password': settings.snowflake_password,
                'warehouse': settings.snowflake_warehouse,
                'database': settings.snowflake_database,
                'schema': settings.snowflake_schema,
                'role': settings.snowflake_role or '',
                'passcode': settings.snowflake_passcode or '',
            }),
            'created_by': 'system',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'last_tested': None,
            'status': 'untested',
        })
        changed = True

    if 'ghl' not in existing_types and settings.ghl_api_key:
        connections.append({
            'id': str(uuid.uuid4()),
            'name': 'Default GoHighLevel (.env)',
            'type': 'ghl',
            'is_default': True,
            'config': _encrypt_config({
                'api_key': settings.ghl_api_key,
                'base_url': settings.ghl_api_base_url,
                'location_id': settings.ghl_location_id or '',
            }),
            'created_by': 'system',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'last_tested': None,
            'status': 'untested',
        })
        changed = True

    if changed:
        _save_connections(connections)


def _test_snowflake(config: Dict[str, str]) -> Dict[str, Any]:
    conn = snowflake.connector.connect(
        account=config.get('account'),
        user=config.get('user'),
        password=config.get('password'),
        warehouse=config.get('warehouse') or None,
        database=config.get('database') or None,
        schema=config.get('schema') or None,
        role=config.get('role') or None,
        passcode=config.get('passcode') or None,
        login_timeout=15,
    )
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT CURRENT_VERSION()')
        version = cursor.fetchone()[0]
        cursor.close()
        return {'ok': True, 'detail': f'Connected (Snowflake {version})'}
    finally:
        conn.close()


def _test_ghl(config: Dict[str, str]) -> Dict[str, Any]:
    base_url = (config.get('base_url') or 'https://services.leadconnectorhq.com').rstrip('/')
    params = {'limit': 1}
    if config.get('location_id'):
        params['locationId'] = config['location_id']
    resp = requests.get(
        f'{base_url}/contacts/',
        headers={
            'Authorization': f"Bearer {config.get('api_key')}",
            'Accept': 'application/json',
        },
        params=params,
        timeout=15,
    )
    if resp.status_code == 200:
        return {'ok': True, 'detail': 'Connected to GoHighLevel API'}
    raise RuntimeError(f'GHL API returned {resp.status_code}: {resp.text[:200]}')


@router.get('')
def list_connections(user: str = Depends(get_current_user)):
    """List all connections with secrets masked"""
    _seed_defaults()
    return [_public_view(c) for c in _load_connections()]


@router.post('')
def create_connection(req: ConnectionCreate, user: str = Depends(get_current_user)):
    """Create a new Snowflake or GHL connection"""
    connections = _load_connections()
    if any(c['name'].lower() == req.name.strip().lower() for c in connections):
        raise HTTPException(status_code=409, detail='A connection with this name already exists')

    if req.type == 'snowflake' and not (req.config.get('passcode') or '').strip():
        raise HTTPException(status_code=422, detail='A passcode (MFA) is required for Snowflake connections')

    conn = {
        'id': str(uuid.uuid4()),
        'name': req.name.strip(),
        'type': req.type,
        'is_default': False,
        'config': _encrypt_config(req.config),
        'created_by': user,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'last_tested': None,
        'status': 'untested',
    }
    connections.append(conn)
    _save_connections(connections)

    hipaa_manager.log_audit_event('connection_created', {
        'connection_id': conn['id'],
        'type': req.type,
        'user': hipaa_manager.mask_sensitive_data(user),
        'timestamp': conn['created_at'],
    })

    return _public_view(conn)


@router.post('/{connection_id}/test')
def test_connection(connection_id: str, user: str = Depends(get_current_user)):
    """Attempt a live connection using the stored credentials"""
    connections = _load_connections()
    conn = next((c for c in connections if c['id'] == connection_id), None)
    if not conn:
        raise HTTPException(status_code=404, detail='Connection not found')

    config = _decrypt_config(conn['config'])
    now = datetime.now(timezone.utc).isoformat()

    try:
        if conn['type'] == 'snowflake':
            result = _test_snowflake(config)
        else:
            result = _test_ghl(config)
        conn['status'] = 'connected'
        conn['last_tested'] = now
        _save_connections(connections)

        hipaa_manager.log_audit_event('connection_test_success', {
            'connection_id': connection_id,
            'type': conn['type'],
            'user': hipaa_manager.mask_sensitive_data(user),
            'timestamp': now,
        })
        return {'status': 'connected', 'detail': result['detail'], 'last_tested': now}

    except Exception as e:
        conn['status'] = 'error'
        conn['last_tested'] = now
        _save_connections(connections)

        hipaa_manager.log_audit_event('connection_test_failed', {
            'connection_id': connection_id,
            'type': conn['type'],
            'error': str(e)[:500],
            'user': hipaa_manager.mask_sensitive_data(user),
            'timestamp': now,
        })
        return {'status': 'error', 'detail': str(e)[:500], 'last_tested': now}


@router.delete('/{connection_id}')
def delete_connection(connection_id: str, user: str = Depends(get_current_user)):
    """Delete a connection (defaults from .env cannot be deleted)"""
    connections = _load_connections()
    conn = next((c for c in connections if c['id'] == connection_id), None)
    if not conn:
        raise HTTPException(status_code=404, detail='Connection not found')
    if conn.get('is_default'):
        raise HTTPException(status_code=400, detail='Default .env connections cannot be deleted')

    _save_connections([c for c in connections if c['id'] != connection_id])

    hipaa_manager.log_audit_event('connection_deleted', {
        'connection_id': connection_id,
        'user': hipaa_manager.mask_sensitive_data(user),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })
    return {'status': 'deleted'}
