# Huawei Credentials

Purpose: document credentials required by the Huawei AppGallery publisher.
Status: stable.
Audience: release engineers and repository administrators.

Huawei documents both modes in [Obtaining Authorization from the Server](https://developer.huawei.com/consumer/en/doc/app/agc-help-connect-api-obtain-server-auth-0000002271134661). Service account mode is Huawei's recommended mode for server-to-server access and is this action's default. Huawei states that service accounts will replace API clients; API client mode remains available here for existing integrations.

## Service Account Mode

1. Sign in to [AppGallery Connect](https://developer.huawei.com/consumer/en/service/josp/agc/index.html) as a user allowed to manage credentials.
2. Open **Users and permissions**, then **API key** > **Connect API** > **Service Account**.
3. Create a **Developer-level** service account. Huawei requires developer-level credentials for Connect API.
4. Assign the least-privileged role that can obtain upload URLs, update app file information, and submit an app for release. Huawei lists account holders, administrators, and app administrators as callers of all required publishing operations. Operations personnel are listed for upload and attachment but not for production submission.
5. Download the generated `******private.json` credential file and store its complete contents as a GitHub secret such as `HUAWEI_SERVICE_ACCOUNT_JSON`.

Use Huawei's [Roles and Permissions](https://developer.huawei.com/consumer/en/doc/app/agc-help-rolepermission-0000002271930352) reference to confirm the role available in your account. Draft-only credentials still need upload URL and app file update permission; production additionally needs app submission permission.

Required secrets:

- `HUAWEI_APP_ID`
- `HUAWEI_CHINESE_MAINLAND_FLAG`
- `HUAWEI_SERVICE_ACCOUNT_JSON`

The service account JSON must include:

- `key_id`
- `private_key`
- `sub_account`
- optionally `token_uri`

If present, `token_uri` must be Huawei's `https://oauth-login.cloud.huawei.com/oauth2/v3/token`. The action signs a one-hour PS256 JWT locally and sends it as a bearer credential; it does not exchange the JWT at that URI.

```yaml
with:
  artifact-path: app-release.aab
  app-id: ${{ secrets.HUAWEI_APP_ID }}
  chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
  auth-mode: service-account
  service-account-json: ${{ secrets.HUAWEI_SERVICE_ACCOUNT_JSON }}
```

## API Client Mode

Only the Huawei team account holder can manage an API client.

1. In AppGallery Connect, open **Users and permissions**, then **API key** > **Connect API** > **API client**.
2. Create a team-level API client and leave **Project** set to `N/A`; Huawei warns that another value causes `403` for these calls.
3. Assign a role with the same publishing permissions described above.
4. Save the displayed client ID and key as separate GitHub secrets.

Set `auth-mode: api-client` and provide both values:

- `client-id`
- `client-secret`

```yaml
with:
  artifact-path: app-release.aab
  app-id: ${{ secrets.HUAWEI_APP_ID }}
  chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
  auth-mode: api-client
  client-id: ${{ secrets.HUAWEI_CLIENT_ID }}
  client-secret: ${{ secrets.HUAWEI_CLIENT_SECRET }}
```

The action requests an access token from `<domain>/oauth2/v1/token` using `client_credentials`, then sends the access token and client ID to Huawei's publishing endpoints.

## Regional Domain

Set `domain` to the site matching the project's AppGallery Connect data processing location:

| Site | Domain |
| --- | --- |
| China | `https://connect-api.cloud.huawei.com/api` |
| Singapore | `https://connect-api-dra.cloud.huawei.com/api` |
| Germany | `https://connect-api-dre.cloud.huawei.com/api` |
| Russia | `https://connect-api-drru.cloud.huawei.com/api` |

China is the default. The action accepts only these official HTTPS endpoints. `chinese-mainland-flag` is a separate required Huawei request value and must be `0` or `1`; choosing a regional domain does not infer it.

## GitHub Secret Protection

Store Huawei credentials in GitHub repository, organization, or environment secrets. For production, prefer an environment with required reviewers and deployment branch restrictions:

```yaml
jobs:
  publish:
    environment: appgallery-production
    runs-on: ubuntu-latest
    steps:
      - uses: irazulabs/actions/publish-to-appgallery@v1
        with:
          artifact-path: app-release.aab
          app-id: ${{ secrets.HUAWEI_APP_ID }}
          chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
          service-account-json: ${{ secrets.HUAWEI_SERVICE_ACCOUNT_JSON }}
```

Examples use `@v1` for readability. Pin the corresponding full release commit SHA in high-assurance production workflows.

## Notes

- Do not commit Huawei credentials.
- Rotate or disable credentials in AppGallery Connect when exposed, and replace the GitHub secret.
- Use a separate, least-privileged credential per trust boundary where practical.
- Dry-run mode does not require auth credentials, but still requires `artifact-path`, `app-id`, and `chinese-mainland-flag`.
- Draft mode is not credential-free: it uploads and attaches to Huawei and therefore requires authentication.
- The action removes known credential environment variables before invoking bundletool and does not intentionally print credentials.
