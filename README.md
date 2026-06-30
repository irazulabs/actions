# Irazu Labs Actions

Purpose: reusable GitHub Actions maintained by Irazu Labs.
Status: pre-release.
Audience: teams publishing mobile apps and automation maintainers.
Links: [action index](docs/action-index.md), [development](docs/development.md), [releasing](docs/releasing.md), [agent instructions](AGENTS.md).

This repository is a public-ready monorepo for Irazu Labs GitHub Actions.

Actions are consumed from subdirectories:

```yaml
uses: irazulabs/actions/publish-to-appgallery@v1
```

## Actions

| Action | Description |
| --- | --- |
| [`publish-to-appgallery`](publish-to-appgallery/README.md) | Publish an Android App Bundle to Huawei AppGallery. |

## Development

```sh
python -m pip install -e publish-to-appgallery[dev]
ruff check publish-to-appgallery
ruff format --check publish-to-appgallery
mypy publish-to-appgallery/src
pytest publish-to-appgallery
```

## Release Model

The repository is intended to use repo-level tags such as `v1`. After a `v1` tag exists, actions can be referenced as `irazulabs/actions/<action>@v1`.

