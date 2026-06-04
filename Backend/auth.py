import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

SECRET_KEY = secrets.token_hex(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200000)
    return h.hex(), salt


def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200000)
    return hmac.compare_digest(h.hex(), stored_hash)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.PyJWTError:
        return None
