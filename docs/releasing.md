# Releasing

Purpose: document release expectations for the public actions monorepo.
Status: stable.
Audience: maintainers.

The `v0.0.1` release dated 2026-06-30 was the initial preview. Releases apply to
every action in this monorepo; the actions are consumed directly from the
repository rather than published through GitHub Marketplace.

## Stable Release

Stable releases publish an immutable semantic version tag and a moving
compatible-major tag.

1. Update every package version, the changelog, and public docs for the release.
2. Merge the release commit to the default branch and confirm validation passes.
3. Manually dispatch [`.github/workflows/release.yml`](../.github/workflows/release.yml)
   from the default branch with `version` set to a version such as `v1.1.0`.
4. Approve the job through the protected `release` environment.
5. Confirm the immutable version tag, `v1` tag, and GitHub Release point to the
   expected commit.

The workflow validates the semantic version and every action, rejects semantic
or commit rollback of the major tag, creates the immutable annotated version
tag, force-moves the `v1` major tag to the same commit, and creates the GitHub
Release. The initial `v1.0.0` run also marked `v0.0.1` as a prerelease.

## Versioning

- Every release receives an immutable semantic version tag such as `v1.0.0`.
- Patch and minor compatible releases move the `v1` tag forward.
- Breaking changes require a new major tag such as `v2`.
- Update root and action-level docs before tagging.

## Consumer References

External consumers should pin actions to the release's full 40-character
commit SHA. Release and major tags are useful for discovery, but a commit SHA
is immutable.

```yaml
uses: irazulabs/actions/publish-to-appgallery@<full-40-character-commit-sha> # v1.0.0
uses: irazulabs/actions/update-gcs-cors@<full-40-character-commit-sha> # v1.1.0
```

Use `git rev-list -n 1 v0.0.1` to resolve the preview tag to its commit. Do not
pin production workflows to a branch.

## Recovery

The workflow is idempotent for the same version and commit. If it fails after
creating the immutable tag, verify that the tag points to the workflow commit,
fix the external cause, and rerun the failed workflow run from the Actions UI.
The rerun preserves the immutable tag, updates the major tag, creates the
release only when missing, and marks the preview as a prerelease.

The workflow fails closed if the requested immutable tag points to another
commit. Never delete or move an immutable semantic version tag. Record a
recovered release failure in the GitHub Release notes.
