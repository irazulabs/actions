# Development

Purpose: describe local development for `publish-to-appgallery`.
Status: stable.
Audience: contributors and agents.

## Setup

```sh
python -m pip install -e .[dev]
```

## Validate

```sh
ruff check .
ruff format --check .
mypy src
pytest
```

## Design Notes

- The action is artifact-first and does not know about EAS build IDs.
- Huawei API calls are isolated behind an injectable transport for unit tests.
- Credentials are accepted through GitHub Action inputs and environment variables, but are not logged.
- Dry-run mode validates the artifact and planned calls without creating an auth context or contacting Huawei.
- Draft mode uploads and attaches but returns before the parsing wait and submit call.
- Production submission is deliberately not retried because a lost response leaves the outcome ambiguous.

## Composite Runtime

Callers do not need to set up Python. `action.yml` uses `actions/setup-python` for Python 3.11, then runs `python -m pip install "${GITHUB_ACTION_PATH}"` before invoking the package. The install can require PyPI access for pinned build and runtime dependencies.

The package uses Python's standard HTTP client for Huawei calls. Java is not a general runtime requirement: the code invokes `java -jar` only when `bundletool-jar` is configured. Otherwise it invokes a `bundletool` executable from `PATH`; failed optional inspection is tolerated unless metadata validation was requested.
