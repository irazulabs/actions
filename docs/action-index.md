# Action Index

Purpose: list available actions and their public usage paths.
Status: stable.
Audience: GitHub Actions users and maintainers.

| Action | Stable reference | Description |
| --- | --- | --- |
| [`publish-to-appgallery`](../publish-to-appgallery/README.md) | `irazulabs/actions/publish-to-appgallery@v1` | Publish an Android App Bundle to Huawei AppGallery. |

External workflows should replace the release tag with its full 40-character
commit SHA:

```yaml
uses: irazulabs/actions/publish-to-appgallery@<full-40-character-commit-sha> # v1.0.0
```

Use GitHub Releases to resolve the current immutable version or commit SHA.
