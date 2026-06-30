# Usage

Purpose: document `publish-to-appgallery` action inputs and outputs.
Status: stable.
Audience: GitHub Actions users.

## Basic Workflow

```yaml
- name: Publish to Huawei AppGallery
  uses: irazulabs/actions/publish-to-appgallery@v1
  with:
    artifact-path: app-release.aab
    app-id: ${{ secrets.HUAWEI_APP_ID }}
    chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
    service-account-json: ${{ secrets.HUAWEI_SERVICE_ACCOUNT_JSON }}
```

## Optional Package Validation

```yaml
with:
  artifact-path: app-release.aab
  app-id: ${{ secrets.HUAWEI_APP_ID }}
  chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
  service-account-json: ${{ secrets.HUAWEI_SERVICE_ACCOUNT_JSON }}
  bundletool-jar: tools/bundletool.jar
  expected-package: com.example.app
  min-version-code: '120'
```

If `expected-package` or `min-version-code` is provided, bundle metadata inspection must succeed.

## Dry Run

```yaml
with:
  artifact-path: app-release.aab
  app-id: ${{ secrets.HUAWEI_APP_ID }}
  chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
  dry-run: 'true'
```

Dry-run mode validates the artifact and prints the planned Huawei operations without uploading or submitting.

