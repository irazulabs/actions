# Publish to Huawei AppGallery

Purpose: publish an Android App Bundle to Huawei AppGallery.
Status: maintained.
Audience: mobile release engineers and GitHub Actions maintainers.
Links: [usage](docs/usage.md), [Huawei credentials](docs/huawei-credentials.md), [EAS and Gradle](docs/eas-integration.md), [recovery](docs/recovery.md), [development](docs/development.md).

`publish-to-appgallery` is an artifact-first GitHub Action. It validates a local `.aab`, uploads it through Huawei's [Publishing API](https://developer.huawei.com/consumer/en/doc/appgallery-connect-references/agcapi-publishing-api-0000002351880118), attaches it to the Huawei release draft, and optionally submits that draft.

It does not build or download the Android artifact. EAS, Gradle, Bitrise, Fastlane, or another earlier step must leave the `.aab` on the runner before this action runs.

This action is consumed directly from the public repository and is not currently listed in GitHub Marketplace. Examples use `@v1` for readability; pin the corresponding full release commit SHA in high-assurance production workflows.

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

Service account authentication is the default and Huawei's recommended mode. Existing API clients are also supported with `auth-mode: api-client`, `client-id`, and `client-secret`. See [Huawei credentials](docs/huawei-credentials.md).

## Release Modes

| Configuration | Huawei mutation | Parsing wait | Submission | `submitted` |
| --- | --- | --- | --- | --- |
| `dry-run: 'true'` | None | No | No | `false` |
| `dry-run: 'false'`, `release-mode: draft` | Uploads and attaches the AAB to the Huawei draft | No | No | `false` |
| `dry-run: 'false'`, `release-mode: production` | Uploads and attaches the AAB | Yes, 120 seconds by default | Yes | `true` after Huawei accepts the submit call |

Draft mode is not a simulation: it mutates the Huawei draft. It deliberately never waits for package parsing and never calls the submit endpoint. `submitted: true` means only that Huawei returned success from the submission API; it does not mean the app is approved, live, or finished with review.

## Validate Only

```yaml
- name: Validate AppGallery submission
  uses: irazulabs/actions/publish-to-appgallery@v1
  with:
    artifact-path: app-release.aab
    app-id: ${{ secrets.HUAWEI_APP_ID }}
    chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
    dry-run: 'true'
```

Dry-run performs local configuration and AAB checks and prints the planned operations. It does not require credentials, authenticate, contact Huawei, upload, attach, wait, or submit. The composite action still sets up Python and installs its package, so GitHub and PyPI access may still be required.

## Requirements

- A local `.aab` produced before this action runs.
- Outbound HTTPS to PyPI during the action's internal installation, the selected Huawei API domain, and Huawei's returned signed OBS upload host. Dry-run does not contact Huawei.
- No caller-managed Python setup: the composite action installs Python 3.11 and its own package.
- Java only when `bundletool-jar` is supplied; the action then runs `java -jar`. Without it, optional metadata inspection uses a `bundletool` executable from `PATH`.
- A protected GitHub environment is recommended for production credentials and approval gates.

## Documentation

- [Inputs, outputs, release modes, validation, retries, and workflow examples](docs/usage.md)
- [Service account and API client setup, roles, regional domains, and secret handling](docs/huawei-credentials.md)
- [Artifact-first EAS and Gradle flows](docs/eas-integration.md)
- [Partial failure recovery and safe retries](docs/recovery.md)
