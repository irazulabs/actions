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

