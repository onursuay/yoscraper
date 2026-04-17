"""JWT-signed unsubscribe token yönetimi (itsdangerous)."""
import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

_SALT    = "unsub-v1"
_MAX_AGE = 60 * 60 * 24 * 365  # 1 yıl


def _serializer():
    secret = os.getenv("FLASK_SECRET_KEY", "ps-dev-secret-change-in-prod")
    return URLSafeTimedSerializer(secret)


def generate_token(email: str) -> str:
    return _serializer().dumps(email.lower().strip(), salt=_SALT)


def verify_token(token: str) -> str | None:
    """Token'ı doğrula ve email döndür. Geçersizse None."""
    try:
        return _serializer().loads(token, salt=_SALT, max_age=_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
