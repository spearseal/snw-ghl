"""
DB connector management.
Stores Snowflake / GoHighLevel connection configs in data/connections.json
with secrets encrypted via the HIPAA compliance manager, and supports
live connection testing.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from config import settings
from hipaa_compliance import hipaa_manager
from snowflake_auth import snowflake_connect, uses_key_pair_auth

logger = logging.getLogger(__name__)

DATA_DIR = os.environ.get(
    'DATA_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
)
CONNECTIONS_FILE = os.path.join(DATA_DIR, 'connections.json')

SECRET_FIELDS = {'password', 'api_key', 'passcode', 'private_key', 'private_key_passphrase'}
MASK_VALUE = '••••••••'

router = APIRouter(prefix='/api/connections', tags=['connections'])


class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: Literal['snowflake', 'ghl']
    config: Dict[str, str]


class ConnectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    config: Optional[Dict[str, str]] = None


class TestConnectionRequest(BaseModel):
    passcode: Optional[str] = Field(default=None, max_length=10)


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


def _merge_config(existing_encrypted: Dict[str, str], new_config: Dict[str, str]) -> Dict[str, str]:
    """Merge an update into an existing (encrypted) config.

    For secret fields, a blank or masked value preserves the existing secret;
    any other value is treated as a new secret and encrypted. Non-secret fields
    are replaced as-is.
    """
    merged = dict(existing_encrypted)
    for k, v in new_config.items():
        if k in SECRET_FIELDS:
            if v and v != MASK_VALUE:
                merged[k] = hipaa_manager.encrypt_data(v)
            # blank/masked -> keep existing encrypted value
        else:
            merged[k] = v
    return merged


def get_active_config(conn_type: str) -> Optional[Dict[str, str]]:
    """Return the decrypted config for the best available connection of a type.

    Preference order: a 'connected' connection, then a default (.env) one,
    then the most recently created. Returns None if none exist.
    """
    conns = [c for c in _load_connections() if c.get('type') == conn_type]
    if not conns:
        return None
    conns.sort(key=lambda c: (
        0 if c.get('status') == 'connected' else 1,
        0 if c.get('is_default') else 1,
        c.get('created_at') or '',
    ))
    return _decrypt_config(conns[0]['config'])


def datasource_configured(conn_type: str) -> bool:
    """Return True if a connection exists or required .env vars are set."""
    if get_active_config(conn_type):
        return True
    if conn_type == 'snowflake':
        if uses_key_pair_auth(get_active_config('snowflake') or {}):
            return bool(settings.snowflake_account and settings.snowflake_user)
        return bool(
            settings.snowflake_account
            and settings.snowflake_user
            and (settings.snowflake_password or settings.snowflake_private_key)
        )
    if conn_type == 'ghl':
        return bool(settings.ghl_api_key)
    return False


def datasource_connected(conn_type: str) -> bool:
    """Return True if a live-tested connection exists for this source type."""
    return any(
        c.get('type') == conn_type and c.get('status') == 'connected'
        for c in _load_connections()
    )


def get_connected_sources() -> Dict[str, bool]:
    """Return which independent datasource types are currently connected."""
    return {
        'snowflake': datasource_connected('snowflake'),
        'ghl': datasource_connected('ghl'),
    }


def snowflake_requires_passcode(config: Optional[Dict[str, str]] = None) -> bool:
    """Return True when the active Snowflake config uses password + MFA auth."""
    cfg = config if config is not None else (get_active_config('snowflake') or {})
    return not uses_key_pair_auth(cfg)


def _validate_snowflake_config(config: Dict[str, str]) -> None:
    """Ensure Snowflake config has credentials for the selected auth method."""
    method = (config.get('auth_method') or '').strip().lower()
    if method not in ('key_pair', 'password', ''):
        raise HTTPException(status_code=422, detail='auth_method must be key_pair or password')

    if uses_key_pair_auth(config):
        from snowflake_auth import get_private_key_pem
        if not get_private_key_pem(config):
            raise HTTPException(
                status_code=422,
                detail='A private key is required for key-pair Snowflake authentication',
            )
        return

    if not (config.get('password') or '').strip():
        raise HTTPException(
            status_code=422,
            detail='Password is required for password-based Snowflake authentication',
        )
    if not (config.get('passcode') or '').strip():
        raise HTTPException(
            status_code=422,
            detail='Passcode (MFA) is required for password-based Snowflake authentication',
        )


def _public_view(conn: Dict[str, Any]) -> Dict[str, Any]:
    """Return a connection with secret fields masked"""
    view = {k: v for k, v in conn.items() if k != 'config'}
    decrypted = _decrypt_config(conn['config'])
    view['config'] = {
        k: ('••••••••' if k in SECRET_FIELDS and v else v)
        for k, v in conn['config'].items()
    }
    if conn.get('type') == 'snowflake':
        view['snowflake_auth_method'] = (
            'key_pair' if uses_key_pair_auth(decrypted) else 'password'
        )
        view['snowflake_requires_passcode'] = not uses_key_pair_auth(decrypted)
    return view


def _seed_defaults():
    """Seed default Snowflake and GHL connections from the .env config"""
    connections = _load_connections()
    existing_types = {c['type'] for c in connections if c.get('is_default')}
    changed = False

    if 'snowflake' not in existing_types and settings.snowflake_account:
        uses_key = bool(settings.snowflake_private_key.strip())
        sf_config = {
            'account': settings.snowflake_account,
            'user': settings.snowflake_user,
            'warehouse': settings.snowflake_warehouse,
            'database': settings.snowflake_database,
            'schema': settings.snowflake_schema,
            'role': settings.snowflake_role or '',
            'custom_tables': settings.snowflake_custom_tables or '',
            'auth_method': 'key_pair' if uses_key else 'password',
            'password': '' if uses_key else settings.snowflake_password,
            'passcode': '' if uses_key else (settings.snowflake_passcode or ''),
            'private_key': settings.snowflake_private_key if uses_key else '',
            'private_key_passphrase': settings.snowflake_private_key_passphrase if uses_key else '',
        }
        if not uses_key and not sf_config['passcode'].strip():
            logger.warning(
                'Snowflake passcode (MFA) not found in .env — '
                'default connection will fail until a passcode is provided.'
            )
        connections.append({
            'id': str(uuid.uuid4()),
            'name': 'Default Snowflake (.env)',
            'type': 'snowflake',
            'is_default': True,
            'config': _encrypt_config(sf_config),
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


def _test_snowflake(config: Dict[str, str], passcode: Optional[str] = None) -> Dict[str, Any]:
    conn = snowflake_connect(config, passcode=passcode, login_timeout=15)
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT CURRENT_VERSION()')
        version = cursor.fetchone()[0]
        cursor.close()
        auth = 'key-pair' if uses_key_pair_auth(config) else 'password'
        return {'ok': True, 'detail': f'Connected via {auth} (Snowflake {version})'}
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

    if req.type == 'snowflake':
        _validate_snowflake_config(req.config)

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


@router.put('/{connection_id}')
def update_connection(connection_id: str, req: ConnectionUpdate, user: str = Depends(get_current_user)):
    """Update a connection's name and/or config.

    Secret fields left blank or masked keep their existing stored value.
    Changing the config resets the connection status to 'untested'.
    """
    connections = _load_connections()
    conn = next((c for c in connections if c['id'] == connection_id), None)
    if not conn:
        raise HTTPException(status_code=404, detail='Connection not found')

    if req.name is not None:
        new_name = req.name.strip()
        if any(c['id'] != connection_id and c['name'].lower() == new_name.lower() for c in connections):
            raise HTTPException(status_code=409, detail='A connection with this name already exists')
        conn['name'] = new_name

    if req.config is not None:
        merged = _merge_config(conn['config'], req.config)
        if conn['type'] == 'snowflake':
            _validate_snowflake_config(_decrypt_config(merged))
        conn['config'] = merged
        conn['status'] = 'untested'
        conn['last_tested'] = None

    _save_connections(connections)

    hipaa_manager.log_audit_event('connection_updated', {
        'connection_id': connection_id,
        'user': hipaa_manager.mask_sensitive_data(user),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })

    return _public_view(conn)


@router.post('/{connection_id}/test')
def test_connection(
    connection_id: str,
    req: TestConnectionRequest = TestConnectionRequest(),
    user: str = Depends(get_current_user),
):
    """Attempt a live connection using the stored credentials"""
    connections = _load_connections()
    conn = next((c for c in connections if c['id'] == connection_id), None)
    if not conn:
        raise HTTPException(status_code=404, detail='Connection not found')

    config = _decrypt_config(conn['config'])
    if conn['type'] == 'snowflake':
        if req.passcode:
            config = {**config, 'passcode': req.passcode.strip()}
        elif uses_key_pair_auth(config):
            pass
        elif not (config.get('passcode') or '').strip():
            return {
                'status': 'error',
                'detail': 'Enter a fresh 6-digit MFA code to test password-based Snowflake auth.',
                'last_tested': datetime.now(timezone.utc).isoformat(),
            }
    now = datetime.now(timezone.utc).isoformat()

    try:
        if conn['type'] == 'snowflake':
            result = _test_snowflake(config, passcode=req.passcode)
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

        detail = str(e)[:500]
        if conn['type'] == 'snowflake' and ('TOTP' in detail or 'passcode' in detail.lower()):
            detail += (
                ' — Enter a fresh 6-digit MFA code from your authenticator '
                '(codes expire every ~30 seconds).'
            )

        hipaa_manager.log_audit_event('connection_test_failed', {
            'connection_id': connection_id,
            'type': conn['type'],
            'error': str(e)[:500],
            'user': hipaa_manager.mask_sensitive_data(user),
            'timestamp': now,
        })
        return {'status': 'error', 'detail': detail, 'last_tested': now}


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
