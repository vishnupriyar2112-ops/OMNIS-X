import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.models import User

bearer = HTTPBearer(auto_error=False)
SECRET = os.getenv("OMNISX_SECRET_KEY")
if not SECRET:
    SECRET = secrets.token_urlsafe(48)
    print("OMNIS-X: generated an in-memory session signing key; sessions expire when the API restarts.")


def verify_password(password, encoded):
    try:
        scheme, salt, expected = encoded.split("$", 2)
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), 310_000
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def issue_token(user):
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({
        "sub": user.email, "role": user.role, "iat": now, "exp": now + 4 * 60 * 60,
    }, separators=(",", ":")).encode())
    body = f"{header}.{payload}"
    signature = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64(signature)}"


def _decode_token(token):
    try:
        header, payload, signature = token.split(".")
        body = f"{header}.{payload}"
        expected = _b64(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        decoded = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(decoded["exp"]) <= int(time.time()):
            raise ValueError("Expired token")
        return decoded
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc


def require_user(credentials: HTTPAuthorizationCredentials, db):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in to continue")
    payload = _decode_token(credentials.credentials)
    user = db.query(User).filter(User.email == payload["sub"], User.is_active.is_(True)).first()
    if user is None or user.role != payload.get("role"):
        raise HTTPException(status_code=401, detail="Invalid or inactive account")
    return user
