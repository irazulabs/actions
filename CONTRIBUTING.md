# Contributing

Thanks for helping improve Irazu Labs Actions.

## Development

Each action is self-contained. Install and validate the action you are changing:

```sh
python -m pip install -e publish-to-appgallery[dev]
ruff check publish-to-appgallery
ruff format --check publish-to-appgallery
mypy publish-to-appgallery/src
pytest publish-to-appgallery
```

## Pull Requests

- Keep public inputs and outputs backward compatible unless the change is explicitly breaking.
- Update the action README and action-specific docs with behavior changes.
- Add unit tests for new failure modes and API behavior.
- Do not include credentials, screenshots with secrets, or live Huawei API payloads.

