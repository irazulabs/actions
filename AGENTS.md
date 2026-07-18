# Irazu Labs Actions Agent Instructions

Purpose: define effective instructions for agents and maintainers working in this repository.
Status: stable.
Audience: AI agents, maintainers, and contributors.
Links: [LLM entrypoint](llms.txt), [docs map](docs/README.md), [action index](docs/action-index.md).

This repository is a public GitHub Actions monorepo. Keep action behavior generic, documented, and safe for public users.

## Work Rules

- Preserve unrelated user changes.
- Keep each action self-contained in its own folder.
- Keep public action inputs stable and documented.
- Do not commit secrets, generated credentials, live API responses, or private app identifiers.
- Prefer small typed Python modules over large scripts.
- Add tests for action metadata, CLI behavior, and external API flows before changing behavior.
- Use official vendor documentation for GitHub Actions and external APIs.

## Validation

Run the relevant action checks before finishing work:

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

## Public Repo Standard

- Root docs explain the monorepo and index all actions.
- Each action folder contains its own `README.md`, `action.yml`, docs, tests, and Python package.
- New actions must be consumable as `irazulabs/actions/<action-name>@v1` after the repo is published and tagged.
