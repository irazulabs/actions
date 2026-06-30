# Releasing

Purpose: document release expectations for the public actions monorepo.
Status: stable.
Audience: maintainers.

This repository is intended to use repo-level major tags such as `v1`.

## First Release

1. Create the public GitHub repository as `irazulabs/actions`.
2. Push `main`.
3. Create an annotated `v1` tag after validation passes.
4. Confirm consumers can use `irazulabs/actions/publish-to-appgallery@v1`.

## Versioning

- Patch and minor compatible changes move the `v1` tag forward.
- Breaking changes require a new major tag such as `v2`.
- Update root and action-level docs before tagging.

