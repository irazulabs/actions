# Huawei Credentials

Purpose: document credentials required by the Huawei AppGallery publisher.
Status: stable.
Audience: release engineers and repository administrators.

## Service Account Mode

Service account mode is the default.

Required secrets:

- `HUAWEI_APP_ID`
- `HUAWEI_CHINESE_MAINLAND_FLAG`
- `HUAWEI_SERVICE_ACCOUNT_JSON`

The service account JSON must include:

- `key_id`
- `private_key`
- `sub_account`
- optionally `token_uri`

## API Client Mode

Set `auth-mode: api-client` and provide:

- `client-id`
- `client-secret`

## Notes

- Do not commit Huawei credentials.
- Prefer GitHub repository or organization secrets.
- Dry-run mode does not require auth credentials, but still requires `artifact-path`, `app-id`, and `chinese-mainland-flag`.

