# Update GCS CORS

Purpose: apply a complete JSON CORS configuration to a Google Cloud Storage bucket.
Status: maintained.
Audience: platform engineers and GitHub Actions maintainers.
Links: [usage](docs/usage.md), [development](docs/development.md).

`update-gcs-cors` validates a local CORS file and runs Google's supported
`gcloud storage buckets update --cors-file` command. The workflow must already
be authenticated to Google Cloud; this action never accepts or creates credentials.

```yaml
- name: Update bucket CORS
  uses: irazulabs/actions/update-gcs-cors@v1
  with:
    bucket: example-project.firebasestorage.app
    cors-file: config/storage-cors.json
```

Examples use `@v1` for readability. Pin the corresponding full release commit
SHA in production workflows.

## Authentication

Authenticate before this action using any method supported by the Google Cloud
CLI. Workload Identity Federation through
[`google-github-actions/auth`](https://github.com/google-github-actions/auth) is
the recommended default because it avoids long-lived service-account keys.

The active identity needs these permissions on the target bucket:

- `storage.buckets.get`
- `storage.buckets.update`

A custom role containing only those permissions is preferred. The predefined
`roles/storage.admin` role also works when granted on the bucket, but is broader.

## CORS File

The file must be the list format expected by `gcloud`, without a top-level
`"cors"` wrapper:

```json
[
  {
    "origin": ["https://www.example.com"],
    "method": ["GET"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
```

An empty list clears the bucket's CORS configuration. Use `dry-run: 'true'` to
validate and report intent without installing `gcloud` or contacting Google Cloud.

See [usage](docs/usage.md) for authentication, IAM, endpoint behavior, outputs,
and production workflow guidance.
