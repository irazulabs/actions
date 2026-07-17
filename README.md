# Irazu Labs Actions

Purpose: reusable GitHub Actions maintained by Irazu Labs.
Status: maintained.
Audience: teams publishing mobile apps and automation maintainers.
Links: [action index](docs/action-index.md), [development](docs/development.md), [releasing](docs/releasing.md), [agent instructions](AGENTS.md).

This public repository is a monorepo for Irazu Labs GitHub Actions. The actions
are consumed directly from this repository, not through GitHub Marketplace.

Actions are consumed from subdirectories:

```yaml
uses: irazulabs/actions/publish-to-appgallery@v1
```

For external workflows, pin the action to the release's full 40-character
commit SHA for an immutable dependency:

```yaml
uses: irazulabs/actions/publish-to-appgallery@<full-40-character-commit-sha> # v1.0.0
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

Stable releases use immutable semantic version tags such as `v1.0.0` and a
moving compatible-major tag such as `v1`. See the repository's GitHub Releases
for currently available versions.

See [releasing](docs/releasing.md) for the manually approved release process
and recovery steps.
