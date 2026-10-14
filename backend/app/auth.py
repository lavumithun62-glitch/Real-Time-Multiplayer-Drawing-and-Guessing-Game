"""Small HS256 JWT implementation using only the Python standard library."""
import base64
import hashlib
import hmac
import json
import time
from .config import settings


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_player_token(player_id: int, room_code: str) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": str(player_id), "room": room_code.upper(), "type": "player", "iat": now, "exp": now + 43200}
    signing_input = f"{_b64encode(json.dumps(header, separators=(',', ':')).encode())}.{_b64encode(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = hmac.new(settings.secret_key.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def verify_player_token(token: str, player_id: int, room_code: str) -> bool:
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}"
        expected = hmac.new(settings.secret_key.encode(), signing_input.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature_part)):
            return False
        header = json.loads(_b64decode(header_part))
        claims = json.loads(_b64decode(payload_part))
        return (
            header.get("alg") == "HS256"
            and claims.get("type") == "player"
            and claims.get("sub") == str(player_id)
            and claims.get("room") == room_code.upper()
            and isinstance(claims.get("exp"), int)
            and claims["exp"] > int(time.time())
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False
