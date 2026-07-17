# EAS and Gradle Integration

Purpose: show how EAS and Gradle users provide an AAB to this artifact-first action.
Status: stable.
Audience: Android and Expo/EAS release engineers.

The publishing action starts at the artifact boundary: `artifact-path` must already point to a local `.aab` on the GitHub runner. It does not accept an EAS build ID, invoke EAS, run Gradle, or download a build.

Examples use `@v1` for readability. Pin the corresponding full release commit SHA in high-assurance production workflows.

## EAS Build

Build with EAS, capture or select the Android build ID in your own workflow, and download the AAB before publishing:

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

`ANDROID_BUILD_ID` is intentionally outside this action's contract. The workflow can obtain it from a prior EAS step, workflow input, or build metadata. Confirm that the selected EAS profile produces an Android App Bundle rather than an APK.

If EAS runs in another job or workflow, upload the resulting AAB as a GitHub artifact there, then download it into the publish job and pass the downloaded path.

## Gradle Build

For a standard Android project, run the bundle task first:

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-java@v4
  with:
    distribution: temurin
    java-version: '17'

- name: Build release AAB
  run: ./gradlew bundleRelease

- name: Publish to Huawei AppGallery
  uses: irazulabs/actions/publish-to-appgallery@v1
  with:
    artifact-path: app/build/outputs/bundle/release/app-release.aab
    app-id: ${{ secrets.HUAWEI_APP_ID }}
    chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
    service-account-json: ${{ secrets.HUAWEI_SERVICE_ACCOUNT_JSON }}
```

The Java setup above belongs to the Android build. The publishing action itself needs Java only if `bundletool-jar` is supplied.

## Separate Build and Publish Jobs

Separating build from release makes the exact reviewed bytes explicit and allows production approval after the AAB exists:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'
      - run: ./gradlew bundleRelease
      - uses: actions/upload-artifact@v4
        with:
          name: android-aab
          path: app/build/outputs/bundle/release/app-release.aab
          if-no-files-found: error

  publish:
    needs: build
    environment: appgallery-production
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: android-aab
          path: dist
      - uses: irazulabs/actions/publish-to-appgallery@v1
        with:
          artifact-path: dist/app-release.aab
          app-id: ${{ secrets.HUAWEI_APP_ID }}
          chinese-mainland-flag: ${{ secrets.HUAWEI_CHINESE_MAINLAND_FLAG }}
          service-account-json: ${{ secrets.HUAWEI_SERVICE_ACCOUNT_JSON }}
```

GitHub artifact storage is only transport between jobs. `publish-to-appgallery` still receives a normal local file and validates and hashes it before any Huawei mutation.
