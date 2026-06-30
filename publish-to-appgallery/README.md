# Publish to Huawei AppGallery

Purpose: publish an Android App Bundle to Huawei AppGallery.
Status: pre-release.
Audience: mobile release engineers and GitHub Actions maintainers.
Links: [usage](docs/usage.md), [Huawei credentials](docs/huawei-credentials.md), [EAS integration](docs/eas-integration.md), [development](docs/development.md).

`publish-to-appgallery` is an artifact-first GitHub Action. It accepts a local `.aab` file and submits it to Huawei AppGallery through Huawei's Publishing API.

It does not build the Android artifact. Build systems such as EAS, Gradle, Bitrise, or Fastlane should create or download the `.aab` before this action runs.

## Usage

```yaml
- name: Publish to Huawei AppGallery
  uses: irazulabs/actions/publish-to-appgallery@v1
  with:
    artifact-path: app/build/outputs/bundle/release/app-release.aab
    app-id: ${{ secrets.HUAWEI_APP_ID }}
    chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
    service-account-json: ${{ secrets.HUAWEI_SERVICE_ACCOUNT_JSON }}
```

## Dry Run

```yaml
- name: Validate AppGallery submission
  uses: irazulabs/actions/publish-to-appgallery@v1
  with:
    artifact-path: app-release.aab
    app-id: ${{ secrets.HUAWEI_APP_ID }}
    chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
    dry-run: 'true'
```

## Outputs

- `artifact-file-name`
- `artifact-path`
- `artifact-sha256`
- `artifact-size-bytes`
- `package-name`
- `version-code`
- `dry-run`
- `object-id`
- `submitted`

