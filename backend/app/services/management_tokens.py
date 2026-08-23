import base64
import hashlib
import hmac
import uuid

from app.core.config import get_settings


def create_management_token(booking_id: uuid.UUID) -> str:
    payload = booking_id.bytes
    signature = hmac.new(
        get_settings().booking_management_signing_key.encode(), payload, hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(payload + signature).decode().rstrip("=")


def booking_id_from_management_token(token: str) -> uuid.UUID | None:
    try:
        decoded = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (ValueError, TypeError):
        return None
    if len(decoded) != 48:
        return None
    payload, supplied_signature = decoded[:16], decoded[16:]
    expected_signature = hmac.new(
        get_settings().booking_management_signing_key.encode(), payload, hashlib.sha256
    ).digest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None
    return uuid.UUID(bytes=payload)


def management_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
