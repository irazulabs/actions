from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from publish_to_appgallery.artifact import ArtifactInfo
from publish_to_appgallery.auth import (
    AuthContext,
    AuthMode,
    create_api_client_auth,
    create_service_account_auth,
)
from publish_to_appgallery.config import PublishConfig


class HuaweiApiError(RuntimeError):
    """Raised when Huawei rejects or fails an API request."""


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None = None


@dataclass(frozen=True)
class HttpResponse:
    status: int
    reason: str
    body: bytes
    headers: dict[str, str]

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


@dataclass(frozen=True)
class PublishResult:
    object_id: str | None
    submitted: bool


Transport = Callable[[HttpRequest], HttpResponse]
Sleeper = Callable[[float], None]


def default_transport(request: HttpRequest) -> HttpResponse:
    urllib_request = urllib.request.Request(
        request.url,
        data=request.body,
        headers=request.headers,
        method=request.method,
    )
    try:
        with urllib.request.urlopen(urllib_request) as response:
            return HttpResponse(
                status=response.status,
                reason=response.reason,
                body=response.read(),
                headers=dict(response.headers),
            )
    except urllib.error.HTTPError as exc:
        return HttpResponse(
            status=exc.code,
            reason=exc.reason,
            body=exc.read(),
            headers=dict(exc.headers),
        )


def default_sleeper(seconds: float) -> None:
    time.sleep(seconds)


def _json_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _append_query(url: str, params: Mapping[str, object | None]) -> str:
    query = {
        key: str(value)
        for key, value in params.items()
        if value is not None and str(value).strip() != ""
    }
    return f"{url}?{urllib.parse.urlencode(query)}"


def _parse_json_response(response: HttpResponse, url: str) -> dict[str, object]:
    text = response.body.decode("utf-8") if response.body else ""
    if not response.ok:
        raise HuaweiApiError(f"Huawei API request failed: {response.status} {response.reason}")
    if text.strip() == "":
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HuaweiApiError(
            f"Huawei API returned non-JSON response from {url}: {text[:240]}"
        ) from exc
    if not isinstance(parsed, dict):
        raise HuaweiApiError(f"Huawei API returned a non-object JSON response from {url}")
    return cast(dict[str, object], parsed)


def _assert_huawei_success(body: Mapping[str, object], operation_name: str) -> None:
    ret = body.get("ret")
    if ret is None:
        return
    parsed_ret = json.loads(ret) if isinstance(ret, str) else ret
    if not isinstance(parsed_ret, Mapping):
        raise HuaweiApiError(f"{operation_name} returned an invalid ret payload")
    code = parsed_ret.get("code")
    if int(str(code)) != 0:
        message = parsed_ret.get("msg") or parsed_ret
        raise HuaweiApiError(f"{operation_name} failed: {message}")


class HuaweiClient:
    def __init__(
        self,
        config: PublishConfig,
        transport: Transport | None = None,
        sleeper: Sleeper | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or default_transport
        self._sleeper = sleeper or default_sleeper

    def publish(self, artifact: ArtifactInfo) -> PublishResult:
        auth_context = self._create_auth_context()
        upload_url_body = self._request_upload_url(artifact, auth_context)
        url_info = upload_url_body.get("urlInfo")
        if not isinstance(url_info, Mapping):
            raise HuaweiApiError("Huawei upload URL response did not include urlInfo.")

        signed_url = _required_mapping_string(url_info, "url")
        object_id = _required_mapping_string(url_info, "objectId")
        upload_method = _optional_mapping_string(url_info, "method") or "PUT"
        upload_headers = _string_mapping(url_info.get("headers"))

        self._upload_artifact(artifact.path, signed_url, upload_method, upload_headers)
        self._update_app_file_info(artifact, object_id, auth_context)
        self._sleeper(float(self._config.parse_wait_seconds))
        self._submit(auth_context)

        return PublishResult(object_id=object_id, submitted=True)

    def _create_auth_context(self) -> AuthContext:
        if self._config.auth_mode is AuthMode.SERVICE_ACCOUNT:
            if self._config.service_account_json is None:
                raise HuaweiApiError("service-account-json is required")
            return create_service_account_auth(self._config.service_account_json)

        if self._config.client_id is None or self._config.client_secret is None:
            raise HuaweiApiError("client-id and client-secret are required")

        token_url = f"{self._config.domain}/oauth2/v1/token"
        body = self._request_json(
            HttpRequest(
                method="POST",
                url=token_url,
                headers={"Content-Type": "application/json"},
                body=_json_bytes(
                    {
                        "client_id": self._config.client_id,
                        "client_secret": self._config.client_secret,
                        "grant_type": "client_credentials",
                    }
                ),
            )
        )
        access_token = body.get("access_token")
        if not isinstance(access_token, str) or access_token.strip() == "":
            raise HuaweiApiError("Huawei API client token response did not include access_token")
        return create_api_client_auth(access_token, self._config.client_id)

    def _request_upload_url(
        self,
        artifact: ArtifactInfo,
        auth_context: AuthContext,
    ) -> dict[str, object]:
        url = _append_query(
            f"{self._config.domain}/publish/v2/upload-url/for-obs",
            {
                "appId": self._config.app_id,
                "chineseMainlandFlag": self._config.chinese_mainland_flag,
                "contentLength": artifact.size_bytes,
                "fileName": artifact.file_name,
                "releaseType": 1,
                "sha256": artifact.sha256,
            },
        )
        body = self._request_json(
            HttpRequest(
                method="GET",
                url=url,
                headers={**auth_context.headers, "Content-Type": "application/json"},
            )
        )
        _assert_huawei_success(body, "Obtaining Huawei upload URL")
        return body

    def _upload_artifact(
        self,
        artifact_path: Path,
        signed_url: str,
        upload_method: str,
        upload_headers: Mapping[str, str],
    ) -> None:
        response = self._transport(
            HttpRequest(
                method=upload_method,
                url=signed_url,
                headers=dict(upload_headers),
                body=artifact_path.read_bytes(),
            )
        )
        if not response.ok:
            raise HuaweiApiError(
                f"Huawei binary upload failed: {response.status} {response.reason}"
            )

    def _update_app_file_info(
        self,
        artifact: ArtifactInfo,
        object_id: str,
        auth_context: AuthContext,
    ) -> None:
        url = _append_query(
            f"{self._config.domain}/publish/v2/app-file-info",
            {"appId": self._config.app_id, "releaseType": 1},
        )
        body = self._request_json(
            HttpRequest(
                method="PUT",
                url=url,
                headers={**auth_context.headers, "Content-Type": "application/json"},
                body=_json_bytes(
                    {
                        "fileType": 5,
                        "files": [{"fileDestUrl": object_id, "fileName": artifact.file_name}],
                    }
                ),
            )
        )
        _assert_huawei_success(body, "Updating Huawei app file information")

    def _submit(self, auth_context: AuthContext) -> None:
        url = _append_query(
            f"{self._config.domain}/publish/v2/app-submit",
            {
                "appId": self._config.app_id,
                "releaseType": 1,
                "remark": self._config.release_remark,
            },
        )
        body = self._request_json(
            HttpRequest(
                method="POST",
                url=url,
                headers={**auth_context.headers, "Content-Type": "application/json"},
                body=_json_bytes({}),
            )
        )
        _assert_huawei_success(body, "Submitting Huawei app for release")

    def _request_json(self, request: HttpRequest) -> dict[str, object]:
        return _parse_json_response(self._transport(request), request.url)


def _required_mapping_string(mapping: Mapping[object, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or value.strip() == "":
        raise HuaweiApiError(f"Huawei response did not include urlInfo.{key}.")
    return value


def _optional_mapping_string(mapping: Mapping[object, object], key: str) -> str | None:
    value = mapping.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, str):
            result[key] = item
    return result
