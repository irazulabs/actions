# Recovery

Purpose: recover safely from partial AppGallery publishing failures.
Status: stable.
Audience: release engineers and incident responders.

The action performs local validation, authentication, upload URL acquisition, binary upload, draft attachment, an optional fixed parsing wait, and production submission in that order. Once upload starts, a failed job can have changed Huawei even though the GitHub step is red.

## First Response

1. Read the stage named in the error: `authentication`, `upload URL acquisition`, `artifact upload`, `app file attachment`, `package parsing wait`, or `app submission`.
2. Record any Huawei object ID in the error. The action includes it after Huawei has returned one, but failed runs do not write normal action outputs.
3. Check the app and release draft in AppGallery Connect before rerunning, especially after attachment or submission.
4. Confirm that the local AAB SHA-256 and intended version are unchanged.
5. If submission failed, determine the Huawei-side release state before any retry. The action intentionally does not retry submission.

## Stage Guide

| Failure stage | Possible Huawei state | Recovery |
| --- | --- | --- |
| Local validation or dry-run | No Huawei mutation. | Fix the configuration, artifact, bundletool, or Java issue and rerun. |
| Authentication | No upload requested by this run. | Check credential JSON or client ID/key, role permissions, credential enablement, runner clock, and regional domain. Then rerun. |
| Upload URL acquisition | Usually no binary upload; Huawei may have allocated an object before a malformed response. | Correct permissions, domain, or transient connectivity and rerun. There is no resume-by-object-ID input. |
| Artifact upload | The object ID was allocated and a partial or complete OBS object may exist, but attachment was not attempted. | Record the object ID, inspect AppGallery Connect if visible, then rerun. The action obtains a new upload URL rather than resuming. |
| App file attachment | The AAB upload completed, but the Huawei draft attachment may or may not have been accepted. | Use the object ID and AppGallery Connect draft to verify attachment. Rerun only if the draft does not already contain the intended artifact or after removing/replacing an unintended draft artifact. |
| Package parsing wait | The upload and draft attachment completed; submission did not run. | Inspect the draft and package parsing state. Submit manually when ready, or rerun knowing that the action will upload and attach again; it cannot submit an existing object ID directly. |
| App submission | Upload and attachment completed. The outcome is unknown after a network failure, server timeout, malformed response, or HTTP 5xx. An explicit Huawei rejection or HTTP 4xx other than 408 is definitive. | For an unknown outcome, check AppGallery Connect before retrying. For a definitive rejection, correct the reported cause first. |

## Draft Runs

A successful `release-mode: draft` run is intentionally partial and returns `submitted: false`. The AAB has been uploaded and attached to the Huawei draft, but the action has not waited for parsing or submitted it. Review and complete the draft manually, or run a later production job after deciding whether another upload and attachment is acceptable.

The action does not expose a mode that submits an existing `object-id`. A production rerun starts the whole remote sequence and can replace or duplicate draft state according to Huawei's handling. Inspect the draft first.

## Retry Behavior

Token acquisition, upload URL acquisition, and draft attachment retry network errors and HTTP `408`, `429`, `500`, `502`, `503`, and `504` up to three total attempts with 1-second and 2-second delays. API calls time out after 30 seconds.

The signed binary upload is attempted once with a 300-second timeout because Huawei upload URLs are valid for only about five minutes. A rerun obtains a fresh URL and object ID.

Submission has one attempt and no automatic retry. If that request times out, loses its response, returns HTTP 408/5xx, or has a malformed response, the action reports that the outcome is unknown and asks you to check AppGallery Connect. Explicit Huawei rejection responses and other HTTP 4xx responses are reported as definitive failures.

## Common Checks

- `401` or authentication failure: verify the service account JSON is complete, the API client key is current, the credential is enabled, and the runner clock is correct.
- `403` or `not allowed`: verify the assigned Huawei role covers upload URL acquisition, app file updates, and production submission. API clients must be team-level with Project `N/A`.
- Regional or token errors: set `domain` to the endpoint matching the project's China, Singapore, Germany, or Russia data processing location.
- Metadata failure: install `bundletool` on `PATH`, or provide `bundletool-jar` and Java, when `expected-package` or `min-version-code` is set.
- Parsing or submit failure: confirm required app metadata is complete in AppGallery Connect and the uploaded AAB has finished processing.
- Repeated network failure: allow outbound HTTPS to PyPI during installation, the selected Huawei API domain, and the signed OBS host returned by Huawei.

Huawei references: [Publishing API](https://developer.huawei.com/consumer/en/doc/appgallery-connect-references/agcapi-publishing-api-0000002351880118), [Updating App File Information](https://developer.huawei.com/consumer/en/doc/appgallery-connect-references/agcapi-app-file-info-0000001111685202), and [Submitting an App for Release](https://developer.huawei.com/consumer/en/doc/appgallery-connect-references/agcapi-app-submit-0000001158245061).
