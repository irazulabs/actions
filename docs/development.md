# Development

Purpose: describe how to work on this actions monorepo.
Status: stable.
Audience: contributors and agents.

Each action owns its runtime package, tests, and docs.

## Validate All Current Actions

```sh
python -m pip install -e publish-to-appgallery[dev]
python -m pip install -e update-gcs-cors[dev]
ruff check publish-to-appgallery
ruff check update-gcs-cors
ruff format --check publish-to-appgallery
ruff format --check update-gcs-cors
mypy publish-to-appgallery/src
mypy update-gcs-cors/src
pytest publish-to-appgallery
pytest update-gcs-cors
```

## Add An Action

1. Create a new action directory at the repo root.
2. Add `action.yml`, `README.md`, action-specific docs, source, and tests.
3. Update [action-index.md](action-index.md) and the root [README](../README.md).
4. Add the action to `.github/workflows/validate.yml`.
