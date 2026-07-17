from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from publish_to_appgallery.auth import DEFAULT_TOKEN_AUDIENCE, create_service_account_jwt


def _decode_segment(segment: str) -> dict[str, object]:
    padded = segment + "=" * (-len(segment) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    parsed = json.loads(decoded)
    assert isinstance(parsed, dict)
    return parsed


def _decode_bytes(segment: str) -> bytes:
    return base64.urlsafe_b64decode((segment + "=" * (-len(segment) % 4)).encode("ascii"))


def service_account() -> tuple[RSAPrivateKey, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return private_key, json.dumps(
        {
            "key_id": "test-key-id",
            "private_key": pem,
            "sub_account": "test-sub-account",
            "token_uri": DEFAULT_TOKEN_AUDIENCE,
        }
    )


def service_account_json() -> str:
    return service_account()[1]


def test_service_account_jwt_has_expected_claims_and_valid_signature() -> None:
    private_key, credentials = service_account()
    jwt = create_service_account_jwt(credentials, issued_at_seconds=1782780000)
    header, payload, signature = jwt.split(".")

    assert _decode_segment(header) == {"alg": "PS256", "kid": "test-key-id", "typ": "JWT"}
    assert _decode_segment(payload) == {
        "aud": DEFAULT_TOKEN_AUDIENCE,
        "exp": 1782783600,
        "iat": 1782780000,
        "iss": "test-sub-account",
    }
    private_key.public_key().verify(
        _decode_bytes(signature),
        f"{header}.{payload}".encode("ascii"),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
        hashes.SHA256(),
    )


def test_service_account_jwt_rejects_invalid_token_uri() -> None:
    _, credentials = service_account()
    parsed = json.loads(credentials)
    parsed["token_uri"] = "https://example.com/token"

    with pytest.raises(ValueError, match="token_uri"):
        create_service_account_jwt(json.dumps(parsed), issued_at_seconds=1782780000)


def test_service_account_jwt_allows_omitted_token_uri() -> None:
    _, credentials = service_account()
    parsed = json.loads(credentials)
    del parsed["token_uri"]

    create_service_account_jwt(json.dumps(parsed), issued_at_seconds=1782780000)
