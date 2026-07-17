# Changelog

All notable changes to this repository will be documented here.

## 1.0.0

- Add draft uploads that attach an AAB without submitting it.
- Validate AAB structure, Huawei inputs, domains, and response contracts.
- Add bounded HTTP retries and timeouts while keeping submission single-attempt.
- Support service-account and API-client authentication across four Huawei regions.
- Make GitHub outputs multiline-safe and add a composite-action smoke test.
- Add a manually approved GitHub workflow for `v1.0.0` and `v1` releases.

## 0.0.1 - 2026-06-30

- Add the `publish-to-appgallery` action for publishing Android App Bundles to Huawei AppGallery.
- Publish the initial preview release for direct repository consumption.
