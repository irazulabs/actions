from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

DEFAULT_TOKEN_AUDIENCE = "https://oauth-login.cloud.huawei.com/oauth2/v3/token"


class AuthMode(StrEnum):
    SERVICE_ACCOUNT = "service-account"
    API_CLIENT = "api-client"


@dataclass(frozen=True)
class AuthContext:
    headers: dict[str, str]
    mode: AuthMode


def _base64_url_json(value: dict[str, object]) -> str:
    encoded = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")


def _base64_url_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _required_string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"service account field {key!r} is required")
    return value.strip()


def _normalize_private_key(value: str) -> bytes:
    if "-----BEGIN PRIVATE KEY-----" in value:
        return value.encode("utf-8")
    return f"-----BEGIN PRIVATE KEY-----\n{value}\n-----END PRIVATE KEY-----\n".encode()


def parse_service_account_json(service_account_json: str) -> dict[str, object]:
    parsed = json.loads(service_account_json)
    if not isinstance(parsed, dict):
        raise ValueError("service account JSON must be an object")
    return cast(dict[str, object], parsed)


def create_service_account_jwt(
    service_account_json: str,
    issued_at_seconds: int | None = None,
) -> str:
    service_account = parse_service_account_json(service_account_json)
    issued_at = issued_at_seconds if issued_at_seconds is not None else int(time.time())
    key_id = _required_string(service_account, "key_id")
    private_key_bytes = _normalize_private_key(_required_string(service_account, "private_key"))
    sub_account = _required_string(service_account, "sub_account")
    token_uri_value = service_account.get("token_uri")
    audience = token_uri_value if isinstance(token_uri_value, str) else DEFAULT_TOKEN_AUDIENCE

    private_key = serialization.load_pem_private_key(private_key_bytes, password=None)
    if not isinstance(private_key, RSAPrivateKey):
        raise ValueError("service account private_key must be an RSA private key")

    header = _base64_url_json({"alg": "PS256", "kid": key_id, "typ": "JWT"})
    payload = _base64_url_json(
        {
            "aud": audience,
            "exp": issued_at + 3600,
            "iat": issued_at,
            "iss": sub_account,
        }
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = private_key.sign(
        signing_input,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
        hashes.SHA256(),
    )

    return f"{header}.{payload}.{_base64_url_bytes(signature)}"


def create_service_account_auth(service_account_json: str) -> AuthContext:
    return AuthContext(
        headers={"Authorization": f"Bearer {create_service_account_jwt(service_account_json)}"},
        mode=AuthMode.SERVICE_ACCOUNT,
    )


def create_api_client_auth(access_token: str, client_id: str) -> AuthContext:
    return AuthContext(
        headers={"Authorization": f"Bearer {access_token}", "client_id": client_id},
        mode=AuthMode.API_CLIENT,
    )
