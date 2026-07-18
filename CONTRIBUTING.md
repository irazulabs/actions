# Contributing

Thanks for helping improve Irazu Labs Actions.

## Development

Each action is self-contained. Install and validate the action you are changing:

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

## Pull Requests

- Keep public inputs and outputs backward compatible unless the change is explicitly breaking.
- Update the action README and action-specific docs with behavior changes.
- Add unit tests for new failure modes and API behavior.
- Do not include credentials, screenshots with secrets, or live Huawei API payloads.
