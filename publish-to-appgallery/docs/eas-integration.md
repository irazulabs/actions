# EAS Integration

Purpose: show how EAS users can provide an AAB to this artifact-first action.
Status: stable.
Audience: Expo/EAS release engineers.

This action does not accept an EAS build ID. Download the EAS artifact first, then pass the local `.aab` path to `artifact-path`.

```yaml
- name: Download EAS Android build
  run: eas build:download --id "$ANDROID_BUILD_ID" --output app-release.aab --non-interactive

- name: Publish to Huawei AppGallery
  uses: irazulabs/actions/publish-to-appgallery@v1
  with:
    artifact-path: app-release.aab
    app-id: ${{ secrets.HUAWEI_APP_ID }}
    chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
    service-account-json: ${{ secrets.HUAWEI_SERVICE_ACCOUNT_JSON }}
```

This keeps the action reusable for any Android build pipeline that can produce an AAB.

