# Native mobile client (Expo / React Native)

This folder contains **store-ready scaffolding**: `package.json`, `app.json`, and **`eas.json`** for [EAS Build](https://docs.expo.dev/build/introduction/) and [EAS Submit](https://docs.expo.dev/submit/introduction/) to **Google Play** and **Apple App Store**.

The web UI remains the primary client until you finish native screens.

## One-time setup

```bash
cd mobile
npm install
npx expo login
eas init   # creates project; paste project ID into app.json -> expo.extra.eas.projectId
```

## Environment

Create `mobile/.env` (gitignored) or use EAS secrets:

```bash
EXPO_PUBLIC_API_BASE=https://api.yourdomain.com
```

Use the same JWT + `X-Tenant-ID` headers as the web app:

- `POST /api/v1/auth/login`
- `GET /api/v1/biomarkers/runs` with `Authorization: Bearer <token>`

## Builds (binaries)

| Command | Purpose |
|---------|---------|
| `eas build --profile development --platform all` | Dev client |
| `eas build --profile preview --platform android` | Internal APK |
| `eas build --profile production --platform all` | **Store binaries** (AAB / IPA) |

## Store submission

1. **Android**: create a Google Play service account JSON; set path in `eas.json` submit block or CI secret `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`.
2. **iOS**: App Store Connect app + Apple Team ID; fill `eas.json` → `submit.production.ios` or pass via `eas submit --latest`.

```bash
eas build --profile production --platform ios
eas submit --platform ios --latest
```

Replace placeholder asset paths in `app.json` (`./assets/icon.png`) with real icons before review.

## Features to mirror

- Run list / status (`/api/biomarkers/runs`, WebSocket `/api/ws/progress/{run_id}`)
- Collaboration (`/api/ws/collab/{session_id}`)

## PWA fallback

`frontend/public/manifest.json` supports installable mobile web without app store review.
