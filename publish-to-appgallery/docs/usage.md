# Usage

Purpose: document `publish-to-appgallery` action inputs and outputs.
Status: stable.
Audience: GitHub Actions users.

The action accepts an existing local Android App Bundle. It does not invoke EAS or Gradle and does not accept an EAS build ID. See [EAS and Gradle integration](eas-integration.md).

Examples use `irazulabs/actions/publish-to-appgallery@v1` for readability. Pin the corresponding full release commit SHA in high-assurance production workflows.

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

This uses the defaults `auth-mode: service-account`, `release-mode: production`, `dry-run: 'false'`, the China API domain, a 150 MiB limit, and a 120-second parsing wait.

## Modes

### Dry-run

```yaml
with:
  artifact-path: app-release.aab
  app-id: ${{ secrets.HUAWEI_APP_ID }}
  chinese-mainland-flag: '0'
  dry-run: 'true'
```

Dry-run validates configuration and the artifact and prints the calls that the selected release mode would make. It creates no authentication context, makes no Huawei or OBS request, does not mutate the Huawei draft, does not wait, and does not submit. Auth inputs may be omitted. Python setup and package installation still run before validation.

### Draft

```yaml
with:
  artifact-path: app-release.aab
  app-id: ${{ secrets.HUAWEI_APP_ID }}
  chinese-mainland-flag: '0'
  service-account-json: ${{ secrets.HUAWEI_SERVICE_ACCOUNT_JSON }}
  release-mode: draft
```

Draft mode authenticates, obtains an upload URL, uploads the AAB, and updates Huawei app file information with the uploaded object. It therefore mutates the Huawei release draft. It never performs the package parsing wait and never calls Huawei's submit endpoint. A successful draft run returns an `object-id` and `submitted: false`.

### Production

Production is the default. It performs the draft operations, waits `parse-wait-seconds`, then calls Huawei's [Submitting an App for Release](https://developer.huawei.com/consumer/en/doc/appgallery-connect-references/agcapi-app-submit-0000001158245061) endpoint once. Production requires a parsing wait of at least 120 seconds.

`submitted: true` means the submit endpoint returned an HTTP success response with Huawei `ret.code` equal to `0`. It does not mean that Huawei review has completed, that the app was approved, or that the release is live.

## Artifact Validation

Every mode, including dry-run, checks that the artifact:

- Has a case-insensitive `.aab` suffix and a filename no longer than 256 characters.
- Is a non-empty file no larger than `max-aab-size-mb`.
- Is an intact ZIP archive with no corrupt member.
- Contains `BundleConfig.pb` and `base/manifest/AndroidManifest.xml`.
- Can be hashed with SHA-256.

These are structural checks, not a complete Android bundle verification.

The action also attempts to read package name and `versionCode` with bundletool:

- With `bundletool-jar`, it runs `java -jar <path> dump manifest` and requires that JAR path to be a file.
- Without `bundletool-jar`, it runs `bundletool dump manifest` from `PATH`.
- Each bundletool command has a 60-second timeout.
- If neither `expected-package` nor `min-version-code` is set, unavailable or failed metadata inspection does not fail the action; `package-name` and `version-code` can be empty.
- If either metadata constraint is set, inspection must succeed and the requested values must match.

The action does not install Java or bundletool. Java is invoked only for the explicit JAR path.

## Inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `artifact-path` | Yes | None | Local path to the AAB. Relative paths resolve from the job workspace. |
| `app-id` | Yes | None | AppGallery Connect app ID, at most 32 characters. |
| `chinese-mainland-flag` | Yes | None | Huawei distribution/account flag; must be the string `0` or `1`. This is independent of `domain`. |
| `auth-mode` | No | `service-account` | `service-account` or `api-client`. |
| `service-account-json` | Conditionally | None | Full Huawei service account credential JSON. Required for a non-dry-run service account run. |
| `client-id` | Conditionally | None | Huawei API client ID. Required for a non-dry-run API client run. |
| `client-secret` | Conditionally | None | Huawei API client secret/key. Required for a non-dry-run API client run. |
| `domain` | No | `https://connect-api.cloud.huawei.com/api` | Exact official Huawei regional API base URL; see [Regional Domains](#regional-domains). |
| `dry-run` | No | `'false'` | Must be the string `'true'` or `'false'`. `'true'` prevents all Huawei calls and mutations. |
| `release-mode` | No | `production` | `draft` uploads and attaches only; `production` also waits and submits. |
| `expected-package` | No | None | Required package ID from bundletool metadata. |
| `min-version-code` | No | None | Non-negative minimum accepted Android `versionCode`; requires bundletool metadata. |
| `max-aab-size-mb` | No | `'150'` | Positive size limit in MiB (`value * 1024 * 1024` bytes). |
| `bundletool-jar` | No | None | Local bundletool JAR path. Uses `java -jar`; otherwise the action tries `bundletool` from `PATH`. |
| `parse-wait-seconds` | No | `'120'` | Fixed wait after attachment and before production submission. Must be at least 120 in production; draft permits zero and does not wait. |
| `release-remark` | No | None | Optional Huawei submit remark, 10 to 300 characters. Used only by production submission. |

## Outputs

Outputs are written after a successful action run. A failed run may print an object ID in its error but does not reach output writing.

| Output | Value |
| --- | --- |
| `artifact-file-name` | Validated AAB filename. |
| `artifact-path` | Resolved local path to the validated AAB. |
| `artifact-sha256` | Lowercase SHA-256 digest. |
| `artifact-size-bytes` | AAB size in bytes. |
| `package-name` | Package ID from bundletool, or empty when metadata was unavailable. |
| `version-code` | Android `versionCode` from bundletool, or empty when metadata was unavailable. |
| `dry-run` | String `true` or `false`. |
| `object-id` | Huawei OBS object ID after upload, or empty for dry-run. |
| `submitted` | String `true` only after a successful production submit response; `false` for dry-run and draft. |

```yaml
- name: Publish to Huawei AppGallery
  id: appgallery
  uses: irazulabs/actions/publish-to-appgallery@v1
  with:
    artifact-path: app-release.aab
    app-id: ${{ secrets.HUAWEI_APP_ID }}
    chinese-mainland-flag: '0'
    service-account-json: ${{ secrets.HUAWEI_SERVICE_ACCOUNT_JSON }}

- name: Record submitted artifact
  env:
    ARTIFACT_SHA256: ${{ steps.appgallery.outputs.artifact-sha256 }}
    ARTIFACT_FILE_NAME: ${{ steps.appgallery.outputs.artifact-file-name }}
  run: |
    printf '%s  %s\n' "$ARTIFACT_SHA256" "$ARTIFACT_FILE_NAME"
```

## Regional Domains

Select the domain matching the AppGallery Connect data processing location. Only these exact HTTPS bases are accepted:

| Site | `domain` |
| --- | --- |
| China | `https://connect-api.cloud.huawei.com/api` |
| Singapore | `https://connect-api-dra.cloud.huawei.com/api` |
| Germany | `https://connect-api-dre.cloud.huawei.com/api` |
| Russia | `https://connect-api-drru.cloud.huawei.com/api` |

Huawei requires the domain to match the project's data processing location. A trailing slash is normalized; other hosts, paths, ports, credentials, queries, fragments, and non-HTTPS URLs are rejected.

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

If `expected-package` or `min-version-code` is provided, bundle metadata inspection must succeed. Supplying a JAR is optional if a working `bundletool` executable is already on `PATH`.

## API Client Authentication

```yaml
with:
  artifact-path: app-release.aab
  app-id: ${{ secrets.HUAWEI_APP_ID }}
  chinese-mainland-flag: '0'
  auth-mode: api-client
  client-id: ${{ secrets.HUAWEI_CLIENT_ID }}
  client-secret: ${{ secrets.HUAWEI_CLIENT_SECRET }}
```

The action exchanges these credentials at `<domain>/oauth2/v1/token`, then sends both the bearer token and `client_id` to the publishing APIs. Service accounts are preferred for new credentials; see [Huawei credentials](huawei-credentials.md).

## Retries and Timeouts

- Huawei API requests use a 30-second request timeout. The signed binary upload uses 300 seconds.
- API-client token acquisition, upload URL acquisition, and app file attachment retry network errors and HTTP `408`, `429`, `500`, `502`, `503`, and `504` up to three total attempts.
- Retry delays are 1 second and then 2 seconds.
- The signed binary upload is attempted once because Huawei upload URLs are short-lived. Rerun the action to acquire a fresh URL after an upload failure.
- Submission is attempted exactly once and is never automatically retried because a lost response makes the outcome ambiguous.
- `parse-wait-seconds` is a fixed delay, not polling and not a request timeout.
- The action does not impose an overall job timeout; set `timeout-minutes` on the GitHub job if required.

See [Recovery](recovery.md) before retrying a partially completed production release.

## Runtime and Network

The composite action internally runs `actions/setup-python` for Python 3.11 and installs itself with pip. Callers do not need a Python setup step. Installation uses the package's pinned build/runtime dependencies and therefore needs outbound PyPI access unless the runner provides an appropriate package mirror or cache. Even dry-run needs this installation path.

Non-dry-run jobs also need outbound HTTPS to the selected Huawei domain and to the HTTPS signed OBS host Huawei returns. API-client mode gets its token from the selected regional domain. Service-account JWT construction is local.

## Protected Production

Keep production credentials in a protected GitHub environment with required reviewers. The environment gate occurs before the job can read its secrets.

```yaml
jobs:
  publish-appgallery:
    environment: appgallery-production
    timeout-minutes: 20
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Download previously built AAB
        uses: actions/download-artifact@v4
        with:
          name: android-aab
          path: dist
      - name: Publish to Huawei AppGallery
        uses: irazulabs/actions/publish-to-appgallery@v1
        with:
          artifact-path: dist/app-release.aab
          app-id: ${{ secrets.HUAWEI_APP_ID }}
          chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
          service-account-json: ${{ secrets.HUAWEI_SERVICE_ACCOUNT_JSON }}
```

Use a separate environment for draft credentials if draft mutation should not share the production approval boundary. Repository administrators configure required reviewers, deployment branch rules, and environment secrets in GitHub, not in this action.
