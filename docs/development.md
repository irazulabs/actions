# Development

Purpose: describe how to work on this actions monorepo.
Status: stable.
Audience: contributors and agents.

Each action owns its runtime package, tests, and docs.

## Validate All Current Actions

```sh
python -m pip install -e publish-to-appgallery[dev]
ruff check publish-to-appgallery
ruff format --check publish-to-appgallery
mypy publish-to-appgallery/src
pytest publish-to-appgallery
```

## Add An Action

1. Create a new action directory at the repo root.
2. Add `action.yml`, `README.md`, action-specific docs, source, and tests.
3. Update [action-index.md](action-index.md) and the root [README](../README.md).
4. Add the action to `.github/workflows/validate.yml`.

