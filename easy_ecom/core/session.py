from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class SessionSigner:
    def __init__(self, secret: str, ttl_seconds: int = 60 * 60 * 12):
        self.secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds

    def dumps(self, payload: dict[str, Any]) -> str:
        body = dict(payload)
        body["exp"] = int(time.time()) + self.ttl_seconds
        encoded = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode("utf-8")).decode("utf-8")
        sig = hmac.new(self.secret, encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{encoded}.{sig}"

    def loads(self, token: str) -> dict[str, Any] | None:
        try:
            encoded, sig = token.rsplit(".", 1)
        except ValueError:
            return None
        expected = hmac.new(self.secret, encoded.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        try:
            payload = json.loads(base64.urlsafe_b64decode(encoded.encode("utf-8")).decode("utf-8"))
        except Exception:
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
