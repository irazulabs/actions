from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from publish_to_appgallery.auth import create_service_account_jwt


def _decode_segment(segment: str) -> dict[str, object]:
    padded = segment + "=" * (-len(segment) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    parsed = json.loads(decoded)
    assert isinstance(parsed, dict)
    return parsed


def service_account_json() -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return json.dumps(
        {
            "key_id": "test-key-id",
            "private_key": pem,
            "sub_account": "test-sub-account",
            "token_uri": "https://oauth-login.cloud.huawei.com/oauth2/v3/token",
        }
    )


def test_service_account_jwt_uses_ps256_header_and_key_id() -> None:
    jwt = create_service_account_jwt(service_account_json(), issued_at_seconds=1782780000)
    header, payload, signature = jwt.split(".")

    assert signature
    assert _decode_segment(header) == {"alg": "PS256", "kid": "test-key-id", "typ": "JWT"}
    assert _decode_segment(payload)["iss"] == "test-sub-account"
