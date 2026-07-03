"""
User authentication for the query app.
JWT-based sessions with PBKDF2 password hashing.
Users are stored locally in data/users.json with salted hashes only.
"""
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from config import settings
from hipaa_compliance import hipaa_manager

DATA_DIR = os.environ.get(
    'DATA_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
)
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
TOKEN_TTL_HOURS = 12
JWT_SECRET = os.environ.get('JWT_SECRET') or settings.encryption_key
JWT_ALGORITHM = 'HS256'

router = APIRouter(prefix='/api/auth', tags=['auth'])
security = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)
    password: str = Field(..., min_length=8, max_length=128)


def _load_users() -> Dict[str, Any]:
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)


def _save_users(users: Dict[str, Any]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        'sha256', password.encode(), bytes.fromhex(salt), 100_000
    ).hex()


def _create_token(email: str) -> str:
    payload = {
        'sub': email,
        'iat': datetime.now(timezone.utc),
        'exp': datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """FastAPI dependency: validates the Bearer token, returns the user email"""
    if credentials is None:
        raise HTTPException(status_code=401, detail='Not authenticated')
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='Session expired')
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail='Invalid token')

    email = payload.get('sub')
    if not email or email not in _load_users():
        raise HTTPException(status_code=401, detail='Unknown user')
    return email


@router.post('/register')
def register(creds: Credentials):
    """Create a new user account"""
    email = creds.email.strip().lower()
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(status_code=422, detail='Invalid email address')

    users = _load_users()
    if email in users:
        raise HTTPException(status_code=409, detail='User already exists')

    salt = secrets.token_hex(16)
    users[email] = {
        'password_hash': _hash_password(creds.password, salt),
        'salt': salt,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    _save_users(users)

    hipaa_manager.log_audit_event('user_registered', {
        'user': hipaa_manager.mask_sensitive_data(email),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })

    return {'token': _create_token(email), 'email': email}


@router.post('/login')
def login(creds: Credentials):
    """Authenticate and receive a JWT"""
    email = creds.email.strip().lower()
    users = _load_users()
    user = users.get(email)

    if not user or not secrets.compare_digest(
        user['password_hash'], _hash_password(creds.password, user['salt'])
    ):
        hipaa_manager.log_audit_event('login_failed', {
            'user': hipaa_manager.mask_sensitive_data(email),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        })
        raise HTTPException(status_code=401, detail='Invalid email or password')

    hipaa_manager.log_audit_event('login_success', {
        'user': hipaa_manager.mask_sensitive_data(email),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })

    return {'token': _create_token(email), 'email': email}


@router.get('/me')
def me(user: str = Depends(get_current_user)):
    """Return the current authenticated user"""
    return {'email': user}
