# Development

Purpose: describe local development for `update-gcs-cors`.
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

The package has no runtime dependencies. Tests inject the command runner and do
not authenticate to Google Cloud or mutate live buckets.
