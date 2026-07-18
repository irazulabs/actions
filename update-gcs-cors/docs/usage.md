# Usage

Purpose: document the `update-gcs-cors` action contract and operational requirements.
Status: stable.
Audience: platform engineers and Google Cloud administrators.

## Existing Authentication

The action uses credentials already recognized by the Google Cloud CLI. It does
not authenticate, select an account, or require a project input.

```yaml
- name: Update bucket CORS
  uses: irazulabs/actions/update-gcs-cors@v1
  with:
    bucket: assets.example.com
    cors-file: config/storage-cors.json
```

The `bucket` input accepts either a bare name or `gs://` bucket URL. The action
updates one bucket per invocation. Use a workflow matrix for multiple buckets.

## Workload Identity Federation

Google's authentication action is the recommended default. It remains a
separate caller-owned step:

```yaml
permissions:
  contents: read
  id-token: write

jobs:
  update-cors:
    runs-on: ubuntu-24.04
    environment: storage-production
    concurrency:
      group: gcs-cors-assets-example
      cancel-in-progress: false
    steps:
      - uses: actions/checkout@v4

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: projects/123456789/locations/global/workloadIdentityPools/github/providers/example
          service_account: storage-cors@example-project.iam.gserviceaccount.com

      - name: Update bucket CORS
        uses: irazulabs/actions/update-gcs-cors@v1
        with:
          bucket: example-project.firebasestorage.app
          cors-file: config/storage-cors.json
```

Pin all production actions to full commit SHAs. Protect production credentials
and OIDC access with environment reviewers, deployment rules, and restricted
Workload Identity Provider conditions.

## IAM

Google requires exactly these permissions to set and view bucket CORS:

- `storage.buckets.get`
- `storage.buckets.update`

Create a project-level custom role in the bucket's project:

```sh
gcloud iam roles create storageCorsUpdater \
  --project=PROJECT_ID \
  --title='Storage CORS Updater' \
  --permissions=storage.buckets.get,storage.buckets.update \
  --stage=GA
```

Grant it to the workflow service account on the individual bucket:

```sh
gcloud storage buckets add-iam-policy-binding gs://BUCKET_NAME \
  --member='serviceAccount:SERVICE_ACCOUNT_EMAIL' \
  --role='projects/PROJECT_ID/roles/storageCorsUpdater'
```

For Workload Identity Federation through a service account, the GitHub identity
also needs `roles/iam.workloadIdentityUser` on that service account. This
impersonation role does not grant bucket access; both bindings are required.

If a custom role is unavailable, `roles/storage.admin` contains the required
permissions and can be granted on the bucket. It also grants broad bucket and
object administration, so avoid granting it project-wide. Object-only roles do
not permit CORS updates.

IAM changes are eventually consistent and can temporarily return `403` after a
new binding is created.

## Inputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `bucket` | Yes | None | Bare bucket name or `gs://` bucket URL. |
| `cors-file` | Yes | None | Local UTF-8 JSON file containing the complete CORS rule list. |
| `dry-run` | No | `'false'` | Validate locally without installing `gcloud` or contacting Google Cloud. |

Relative CORS paths resolve from `GITHUB_WORKSPACE`. The file is applied as
complete desired state, not merged with existing rules. A top-level `[]` clears
all bucket CORS rules.

## Outputs

| Output | Value |
| --- | --- |
| `bucket` | Normalized bare bucket name. |
| `cors-file` | Resolved CORS file path. |
| `cors-sha256` | SHA-256 of the exact validated file bytes. |
| `rule-count` | Number of desired CORS rules. |
| `dry-run` | String `true` or `false`. |

## Endpoint Behavior

Bucket CORS configuration governs Cloud Storage XML API endpoints such as
`storage.googleapis.com/BUCKET_NAME`. JSON API endpoints have separate CORS
behavior, and `storage.cloud.google.com` does not support CORS requests.

## Failures And Retries

The action does not add retries around `gcloud`. Applying the same complete
policy is idempotent, so inspect the bucket after an ambiguous network failure
and rerun when appropriate:

```sh
gcloud storage buckets describe gs://BUCKET_NAME --format='default(cors_config)'
```

Concurrent updates are last-writer-wins. Serialize workflows targeting the same
bucket with a GitHub `concurrency` group.
