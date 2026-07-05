"""
Shared Snowflake authentication helpers.
Supports password + MFA passcode or RSA key-pair (service user) login.
"""
from typing import Any, Dict, Optional

import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from config import settings


def _resolve(config: Dict[str, str], key: str, env_default: str = '') -> str:
    return (config.get(key) or env_default or '').strip()


def normalize_pem(pem: str) -> str:
    """Restore newlines when a PEM key is stored as a single-line env var."""
    text = (pem or '').strip()
    if '\\n' in text:
        text = text.replace('\\n', '\n')
    return text


def get_private_key_pem(config: Optional[Dict[str, str]] = None) -> str:
    cfg = config or {}
    env_key = normalize_pem(settings.snowflake_private_key)
    if env_key and not cfg.get('private_key'):
        return env_key
    return normalize_pem(cfg.get('private_key', ''))


def uses_key_pair_auth(config: Optional[Dict[str, str]] = None) -> bool:
    """Return True when the config should authenticate with an RSA private key."""
    cfg = config or {}
    method = (cfg.get('auth_method') or '').strip().lower()
    if method == 'key_pair':
        return True
    if method == 'password':
        return False
    if get_private_key_pem(cfg):
        return True
    return bool(normalize_pem(settings.snowflake_private_key))


def load_private_key_bytes(pem: str, passphrase: Optional[str] = None) -> bytes:
    pem = normalize_pem(pem)
    if not pem:
        raise ValueError('Snowflake private key is empty')

    pwd = passphrase.encode() if passphrase else None
    key = serialization.load_pem_private_key(
        pem.encode(),
        password=pwd,
        backend=default_backend(),
    )
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def snowflake_connect_kwargs(
    config: Optional[Dict[str, str]] = None,
    *,
    passcode: Optional[str] = None,
    login_timeout: int = 15,
) -> Dict[str, Any]:
    """Build keyword arguments for snowflake.connector.connect()."""
    cfg = dict(config or {})

    kwargs: Dict[str, Any] = {
        'account': _resolve(cfg, 'account', settings.snowflake_account),
        'user': _resolve(cfg, 'user', settings.snowflake_user),
        'warehouse': _resolve(cfg, 'warehouse', settings.snowflake_warehouse) or None,
        'database': _resolve(cfg, 'database', settings.snowflake_database) or None,
        'schema': _resolve(cfg, 'schema', settings.snowflake_schema) or None,
        'role': _resolve(cfg, 'role', settings.snowflake_role or '') or None,
        'login_timeout': login_timeout,
    }

    if uses_key_pair_auth(cfg):
        pem = get_private_key_pem(cfg)
        passphrase = _resolve(
            cfg,
            'private_key_passphrase',
            settings.snowflake_private_key_passphrase,
        ) or None
        kwargs['private_key'] = load_private_key_bytes(pem, passphrase)
        return kwargs

    password = _resolve(cfg, 'password', settings.snowflake_password)
    if not password:
        raise ValueError('Snowflake password is required for password-based authentication')

    kwargs['password'] = password
    effective_passcode = (passcode or '').strip() or _resolve(
        cfg, 'passcode', settings.snowflake_passcode
    ) or None
    if effective_passcode:
        kwargs['passcode'] = effective_passcode
    return kwargs


def snowflake_connect(
    config: Optional[Dict[str, str]] = None,
    *,
    passcode: Optional[str] = None,
    login_timeout: int = 15,
):
    return snowflake.connector.connect(
        **snowflake_connect_kwargs(config, passcode=passcode, login_timeout=login_timeout)
    )
