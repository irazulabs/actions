from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from publish_to_appgallery.artifact import ArtifactInfo
from publish_to_appgallery.auth import (
    AuthContext,
    AuthMode,
    create_api_client_auth,
    create_service_account_auth,
)
from publish_to_appgallery.config import PublishConfig, ReleaseMode

API_TIMEOUT_SECONDS = 30.0
UPLOAD_TIMEOUT_SECONDS = 300.0
MAX_ATTEMPTS = 3
RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_DIAGNOSTIC_LENGTH = 200


class HuaweiApiError(RuntimeError):
    """Raised when Huawei rejects or fails an API request."""


class HuaweiRejectedError(HuaweiApiError):
    """Raised when Huawei explicitly rejects an API request."""


class HuaweiHttpError(HuaweiApiError):
    """Raised when Huawei returns a non-success HTTP response."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None = None
    timeout: float = API_TIMEOUT_SECONDS


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


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirectHandler())


def default_transport(request: HttpRequest) -> HttpResponse:
    urllib_request = urllib.request.Request(
        request.url,
        data=request.body,
        headers=request.headers,
        method=request.method,
    )
    try:
        with _NO_REDIRECT_OPENER.open(urllib_request, timeout=request.timeout) as response:
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


def _safe_diagnostic(value: object) -> str:
    text = " ".join(str(value).split())
    text = re.sub(r"https?://[^\s\"'<>]+", "[redacted URL]", text, flags=re.IGNORECASE)
    return text[:MAX_DIAGNOSTIC_LENGTH]


def _parse_json_response(
    response: HttpResponse,
    *,
    include_error_body: bool,
) -> dict[str, object]:
    text = response.body.decode("utf-8", errors="replace") if response.body else ""
    if not response.ok:
        reason = _safe_diagnostic(response.reason)
        detail = _safe_diagnostic(text) if include_error_body and text.strip() else ""
        raise HuaweiHttpError(
            f"Huawei API request failed: {response.status}{f' {reason}' if reason else ''}"
            f"{f': {detail}' if detail else ''}",
            response.status,
        )
    if text.strip() == "":
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HuaweiApiError("Huawei API returned a non-JSON response") from exc
    if not isinstance(parsed, dict):
        raise HuaweiApiError("Huawei API returned a non-object JSON response")
    return cast(dict[str, object], parsed)


def _assert_huawei_success(body: Mapping[str, object], operation_name: str) -> None:
    ret = body.get("ret")
    if ret is None:
        raise HuaweiApiError(f"{operation_name} did not return a ret code")
    try:
        parsed_ret = json.loads(ret) if isinstance(ret, str) else ret
    except (json.JSONDecodeError, TypeError) as exc:
        raise HuaweiApiError(f"{operation_name} returned an invalid ret payload") from exc
    if not isinstance(parsed_ret, Mapping):
        raise HuaweiApiError(f"{operation_name} returned an invalid ret payload")
    code = parsed_ret.get("code")
    try:
        parsed_code = int(str(code))
    except (TypeError, ValueError) as exc:
        raise HuaweiApiError(f"{operation_name} returned an invalid ret code") from exc
    if isinstance(code, bool) or parsed_code != 0:
        message = _safe_diagnostic(parsed_ret.get("msg") or "Huawei rejected the request")
        raise HuaweiRejectedError(f"{operation_name} failed: {message}")


def _stage_error(
    stage: str,
    error: Exception,
    *,
    object_id: str | None = None,
    ambiguous_submission: bool = False,
) -> HuaweiApiError:
    object_context = (
        f" for object ID {_safe_diagnostic(object_id)}" if object_id is not None else ""
    )
    guidance = (
        " Submission outcome is unknown; check AppGallery Connect before retrying."
        if ambiguous_submission
        else ""
    )
    return HuaweiApiError(
        f"Huawei {stage} failed{object_context}: {_safe_diagnostic(error)}.{guidance}"
    )


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
        try:
            auth_context = self._create_auth_context()
        except Exception as exc:
            raise _stage_error("authentication", exc) from exc

        object_id: str | None = None
        try:
            upload_url_body = self._request_upload_url(artifact, auth_context)
            url_info = upload_url_body.get("urlInfo")
            if not isinstance(url_info, Mapping):
                raise HuaweiApiError("Huawei upload URL response did not include urlInfo")
            signed_url = _required_mapping_string(url_info, "url")
            object_id = _required_mapping_string(url_info, "objectId")
            upload_method = _optional_mapping_string(url_info, "method") or "PUT"
            upload_headers = _string_mapping(url_info.get("headers"))
            _validate_upload_target(signed_url, upload_method)
        except Exception as exc:
            raise _stage_error("upload URL acquisition", exc, object_id=object_id) from exc

        try:
            self._upload_artifact(artifact.path, signed_url, upload_headers)
        except Exception as exc:
            raise _stage_error("artifact upload", exc, object_id=object_id) from exc

        try:
            self._update_app_file_info(artifact, object_id, auth_context)
        except Exception as exc:
            raise _stage_error("app file attachment", exc, object_id=object_id) from exc

        if self._config.release_mode is ReleaseMode.DRAFT:
            return PublishResult(object_id=object_id, submitted=False)

        try:
            self._sleeper(float(self._config.parse_wait_seconds))
        except Exception as exc:
            raise _stage_error("package parsing wait", exc, object_id=object_id) from exc
        try:
            self._submit(auth_context)
        except Exception as exc:
            raise _stage_error(
                "app submission",
                exc,
                object_id=object_id,
                ambiguous_submission=_submission_outcome_is_ambiguous(exc),
            ) from exc

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
            ),
            retry=True,
            include_error_body=False,
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
            ),
            retry=True,
        )
        _assert_huawei_success(body, "Obtaining Huawei upload URL")
        return body

    def _upload_artifact(
        self,
        artifact_path: Path,
        signed_url: str,
        upload_headers: Mapping[str, str],
    ) -> None:
        response = self._send(
            HttpRequest(
                method="PUT",
                url=signed_url,
                headers=dict(upload_headers),
                body=artifact_path.read_bytes(),
                timeout=UPLOAD_TIMEOUT_SECONDS,
            ),
            retry=False,
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
            ),
            retry=True,
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
            ),
            retry=False,
        )
        _assert_huawei_success(body, "Submitting Huawei app for release")

    def _request_json(
        self,
        request: HttpRequest,
        *,
        retry: bool,
        include_error_body: bool = True,
    ) -> dict[str, object]:
        return _parse_json_response(
            self._send(request, retry=retry),
            include_error_body=include_error_body,
        )

    def _send(self, request: HttpRequest, *, retry: bool) -> HttpResponse:
        attempts = MAX_ATTEMPTS if retry else 1
        for attempt in range(attempts):
            try:
                response = self._transport(request)
            except OSError as exc:
                if attempt + 1 == attempts:
                    raise HuaweiApiError(
                        f"Huawei request failed after {attempts} attempt(s) due to a network error"
                    ) from exc
            else:
                if response.status not in RETRYABLE_STATUSES or attempt + 1 == attempts:
                    return response
            self._sleeper(float(2**attempt))
        raise AssertionError("retry loop did not return or raise")


def _required_mapping_string(mapping: Mapping[object, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or value.strip() == "":
        raise HuaweiApiError(f"Huawei response did not include urlInfo.{key}.")
    return value


def _validate_upload_target(signed_url: str, method: str) -> None:
    try:
        parsed = urllib.parse.urlsplit(signed_url)
        port = parsed.port
    except ValueError as exc:
        raise HuaweiApiError("Huawei returned an invalid signed upload URL") from exc
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or port == 0
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or any(character.isspace() for character in signed_url)
    ):
        raise HuaweiApiError("Huawei returned an invalid signed upload URL")
    if method.strip().upper() != "PUT":
        raise HuaweiApiError("Huawei returned an invalid signed upload method; expected PUT")


def _submission_outcome_is_ambiguous(error: Exception) -> bool:
    if isinstance(error, HuaweiRejectedError):
        return False
    if isinstance(error, HuaweiHttpError):
        return not (400 <= error.status < 500 and error.status != 408)
    return True


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
