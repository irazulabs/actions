from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from publish_to_appgallery.auth import AuthMode
from publish_to_appgallery.cli import publish
from publish_to_appgallery.client import HttpRequest, HttpResponse, HuaweiApiError
from publish_to_appgallery.config import ReleaseMode

from .conftest import make_config, metadata_runner
from .test_auth import service_account_json


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[HttpRequest] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.calls.append(request)
        if "/publish/v2/upload-url/for-obs" in request.url:
            return json_response(
                {
                    "ret": {"code": 0, "msg": "success"},
                    "urlInfo": {
                        "objectId": "uploaded-object-id.aab",
                        "url": "https://upload.example/uploaded-object-id.aab",
                        "method": "PUT",
                        "headers": {"Content-Type": "application/octet-stream"},
                    },
                }
            )
        if request.url == "https://upload.example/uploaded-object-id.aab":
            return json_response({})
        if "/publish/v2/app-file-info" in request.url:
            return json_response({"ret": {"code": 0, "msg": "success"}})
        if "/publish/v2/app-submit" in request.url:
            return json_response({"ret": {"code": 0, "msg": "success"}})
        raise AssertionError(f"unexpected request: {request.url}")


def json_response(body: object, status: int = 200, reason: str = "OK") -> HttpResponse:
    return HttpResponse(
        status=status,
        reason=reason,
        body=json.dumps(body).encode("utf-8"),
        headers={},
    )


def test_huawei_api_sequence_uploads_updates_waits_and_submits(artifact_path: Path) -> None:
    transport = FakeTransport()
    waits: list[float] = []
    config = make_config(
        artifact_path,
        dry_run=False,
        service_account_json=service_account_json(),
        release_remark="Automated release",
    )

    summary = publish(
        config,
        command_runner=metadata_runner(),
        transport=transport,
        sleeper=waits.append,
    )

    assert summary["submitted"] is True
    assert waits == [0.0]
    assert [call.method for call in transport.calls] == ["GET", "PUT", "PUT", "POST"]
    assert [call.timeout for call in transport.calls] == [30.0, 300.0, 30.0, 30.0]
    assert "/upload-url/for-obs" in transport.calls[0].url
    assert transport.calls[1].url == "https://upload.example/uploaded-object-id.aab"
    assert "/app-file-info" in transport.calls[2].url
    assert "/app-submit" in transport.calls[3].url


def test_api_client_auth_obtains_token_and_sends_client_id(artifact_path: Path) -> None:
    calls: list[HttpRequest] = []

    def transport(request: HttpRequest) -> HttpResponse:
        calls.append(request)
        if "/oauth2/v1/token" in request.url:
            assert request.method == "POST"
            assert json.loads((request.body or b"{}").decode("utf-8")) == {
                "client_id": "client-id",
                "client_secret": "client-secret",
                "grant_type": "client_credentials",
            }
            return json_response({"access_token": "api-client-token"})
        return FakeTransport()(request)

    config = make_config(
        artifact_path,
        auth_mode=AuthMode.API_CLIENT,
        client_id="client-id",
        client_secret="client-secret",
        dry_run=False,
    )

    publish(config, command_runner=metadata_runner(), transport=transport, sleeper=lambda _: None)

    assert calls[0].url.endswith("/oauth2/v1/token")
    assert any(call.headers.get("client_id") == "client-id" for call in calls)
    assert any(call.headers.get("Authorization") == "Bearer api-client-token" for call in calls)


def test_draft_uploads_and_attaches_without_waiting_or_submitting(artifact_path: Path) -> None:
    transport = FakeTransport()
    waits: list[float] = []

    summary = publish(
        make_config(
            artifact_path,
            dry_run=False,
            service_account_json=service_account_json(),
            release_mode=ReleaseMode.DRAFT,
        ),
        command_runner=metadata_runner(),
        transport=transport,
        sleeper=waits.append,
    )

    assert summary["objectId"] == "uploaded-object-id.aab"
    assert summary["submitted"] is False
    assert waits == []
    assert [call.method for call in transport.calls] == ["GET", "PUT", "PUT"]


def test_production_wait_failure_does_not_submit(artifact_path: Path) -> None:
    transport = FakeTransport()

    def fail_wait(_seconds: float) -> None:
        raise RuntimeError("interrupted")

    with pytest.raises(HuaweiApiError) as error:
        publish(
            make_config(
                artifact_path,
                dry_run=False,
                service_account_json=service_account_json(),
            ),
            command_runner=metadata_runner(),
            transport=transport,
            sleeper=fail_wait,
        )

    assert "package parsing wait" in str(error.value)
    assert "object ID uploaded-object-id.aab" in str(error.value)
    assert [call.method for call in transport.calls] == ["GET", "PUT", "PUT"]


def test_huawei_ret_code_failure_is_reported(artifact_path: Path) -> None:
    def transport(_request: HttpRequest) -> HttpResponse:
        return json_response({"ret": {"code": 1, "msg": "not allowed"}})

    config = make_config(
        artifact_path,
        dry_run=False,
        service_account_json=service_account_json(),
    )

    with pytest.raises(HuaweiApiError, match="not allowed"):
        publish(
            config, command_runner=metadata_runner(), transport=transport, sleeper=lambda _: None
        )


@pytest.mark.parametrize("ret", [None, {}, {"code": None}, "not-json"])
def test_huawei_ret_code_is_mandatory_and_valid(artifact_path: Path, ret: object) -> None:
    def transport(_request: HttpRequest) -> HttpResponse:
        return json_response({} if ret is None else {"ret": ret})

    with pytest.raises(HuaweiApiError, match="ret (code|payload)"):
        publish(
            make_config(
                artifact_path,
                dry_run=False,
                service_account_json=service_account_json(),
            ),
            command_runner=metadata_runner(),
            transport=transport,
            sleeper=lambda _: None,
        )


def test_http_error_is_reported(artifact_path: Path) -> None:
    def transport(_request: HttpRequest) -> HttpResponse:
        return json_response({"error": "bad"}, status=500, reason="Server Error")

    config = make_config(
        artifact_path,
        dry_run=False,
        service_account_json=service_account_json(),
    )

    with pytest.raises(HuaweiApiError, match='500 Server Error.*"error": "bad"'):
        publish(
            config, command_runner=metadata_runner(), transport=transport, sleeper=lambda _: None
        )


def test_non_json_response_is_reported(artifact_path: Path) -> None:
    def transport(_request: HttpRequest) -> HttpResponse:
        return HttpResponse(status=200, reason="OK", body=b"not json", headers={})

    config = make_config(
        artifact_path,
        dry_run=False,
        service_account_json=service_account_json(),
    )

    with pytest.raises(HuaweiApiError, match="non-JSON"):
        publish(
            config, command_runner=metadata_runner(), transport=transport, sleeper=lambda _: None
        )


@pytest.mark.parametrize(
    ("signed_url", "method"),
    [
        ("http://upload.example/file.aab", "PUT"),
        ("https://user:password@upload.example/file.aab", "PUT"),
        ("https://upload.example/file.aab#fragment", "PUT"),
        ("https://upload.example/file.aab", "POST"),
    ],
)
def test_signed_upload_target_is_restricted(
    artifact_path: Path, signed_url: str, method: str
) -> None:
    def transport(request: HttpRequest) -> HttpResponse:
        assert "/upload-url/for-obs" in request.url
        return json_response(
            {
                "ret": {"code": 0},
                "urlInfo": {
                    "objectId": "uploaded-object-id.aab",
                    "url": signed_url,
                    "method": method,
                },
            }
        )

    with pytest.raises(HuaweiApiError, match="invalid signed upload") as error:
        publish(
            make_config(
                artifact_path,
                dry_run=False,
                service_account_json=service_account_json(),
            ),
            command_runner=metadata_runner(),
            transport=transport,
            sleeper=lambda _: None,
        )

    assert signed_url not in str(error.value)


@pytest.mark.parametrize(
    "target",
    [
        "/oauth2/v1/token",
        "/publish/v2/upload-url/for-obs",
        "/publish/v2/app-file-info",
    ],
)
def test_retryable_calls_stop_after_three_attempts(artifact_path: Path, target: str) -> None:
    base_transport = FakeTransport()
    attempts = 0
    waits: list[float] = []

    def transport(request: HttpRequest) -> HttpResponse:
        nonlocal attempts
        if target in request.url:
            attempts += 1
            if attempts < 3:
                return json_response({}, status=503, reason="Unavailable")
        if "/oauth2/v1/token" in request.url:
            return json_response({"access_token": "api-client-token"})
        return base_transport(request)

    publish(
        make_config(
            artifact_path,
            auth_mode=AuthMode.API_CLIENT if "token" in target else AuthMode.SERVICE_ACCOUNT,
            client_id="client-id" if "token" in target else None,
            client_secret="client-secret" if "token" in target else None,
            service_account_json=None if "token" in target else service_account_json(),
            dry_run=False,
            release_mode=ReleaseMode.DRAFT,
        ),
        command_runner=metadata_runner(),
        transport=transport,
        sleeper=waits.append,
    )

    assert attempts == 3
    assert waits == [1.0, 2.0]


def test_signed_upload_is_not_retried(artifact_path: Path) -> None:
    base_transport = FakeTransport()
    attempts = 0

    def transport(request: HttpRequest) -> HttpResponse:
        nonlocal attempts
        if request.url == "https://upload.example/uploaded-object-id.aab":
            attempts += 1
            return json_response(
                {"Authorization": "temporary-secret"},
                status=503,
                reason="Unavailable",
            )
        return base_transport(request)

    with pytest.raises(HuaweiApiError, match="artifact upload") as error:
        publish(
            make_config(
                artifact_path,
                dry_run=False,
                service_account_json=service_account_json(),
                release_mode=ReleaseMode.DRAFT,
            ),
            command_runner=metadata_runner(),
            transport=transport,
            sleeper=lambda _: None,
        )

    assert attempts == 1
    assert "temporary-secret" not in str(error.value)


def test_network_errors_are_retried_without_leaking_details(artifact_path: Path) -> None:
    attempts = 0

    def transport(_request: HttpRequest) -> HttpResponse:
        nonlocal attempts
        attempts += 1
        raise urllib.error.URLError("client-secret https://signed.example/private?token=secret")

    with pytest.raises(HuaweiApiError) as error:
        publish(
            make_config(
                artifact_path,
                dry_run=False,
                service_account_json=service_account_json(),
            ),
            command_runner=metadata_runner(),
            transport=transport,
            sleeper=lambda _: None,
        )

    assert attempts == 3
    assert "client-secret" not in str(error.value)
    assert "signed.example" not in str(error.value)


def test_submit_is_not_retried_and_reports_ambiguous_recovery(artifact_path: Path) -> None:
    base_transport = FakeTransport()
    submit_attempts = 0

    def transport(request: HttpRequest) -> HttpResponse:
        nonlocal submit_attempts
        if "/publish/v2/app-submit" in request.url:
            submit_attempts += 1
            return json_response({}, status=503, reason="Unavailable")
        return base_transport(request)

    with pytest.raises(HuaweiApiError) as error:
        publish(
            make_config(
                artifact_path,
                dry_run=False,
                service_account_json=service_account_json(),
            ),
            command_runner=metadata_runner(),
            transport=transport,
            sleeper=lambda _: None,
        )

    message = str(error.value)
    assert submit_attempts == 1
    assert "object ID uploaded-object-id.aab" in message
    assert "outcome is unknown" in message
    assert "before retrying" in message


def test_explicit_submit_rejection_is_not_reported_as_ambiguous(artifact_path: Path) -> None:
    base_transport = FakeTransport()

    def transport(request: HttpRequest) -> HttpResponse:
        if "/publish/v2/app-submit" in request.url:
            return json_response({"ret": {"code": 1, "msg": "package is not ready"}})
        return base_transport(request)

    with pytest.raises(HuaweiApiError) as error:
        publish(
            make_config(
                artifact_path,
                dry_run=False,
                service_account_json=service_account_json(),
            ),
            command_runner=metadata_runner(),
            transport=transport,
            sleeper=lambda _: None,
        )

    message = str(error.value)
    assert "package is not ready" in message
    assert "outcome is unknown" not in message


def test_submit_http_client_error_is_not_reported_as_ambiguous(artifact_path: Path) -> None:
    base_transport = FakeTransport()

    def transport(request: HttpRequest) -> HttpResponse:
        if "/publish/v2/app-submit" in request.url:
            return json_response({"error": "forbidden"}, status=403, reason="Forbidden")
        return base_transport(request)

    with pytest.raises(HuaweiApiError) as error:
        publish(
            make_config(
                artifact_path,
                dry_run=False,
                service_account_json=service_account_json(),
            ),
            command_runner=metadata_runner(),
            transport=transport,
            sleeper=lambda _: None,
        )

    message = str(error.value)
    assert "403 Forbidden" in message
    assert "outcome is unknown" not in message
