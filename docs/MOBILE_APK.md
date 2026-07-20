# Universal Soul — Android APK shell (Capacitor)

Local-first phone app that wraps the PWA and talks to your **PC brain**
(`python scripts/serve_pwa.py --host 0.0.0.0 --port 8765`).

## What you get

- Installable Android app (`com.universalsoul.companion`)
- Same companion UI as the PWA (library, storyteller, emotion eyes)
- **Home-screen widget** with companion face / emotion eyes (tap opens the app)
- Settings → **PC brain URL** (required in the APK), e.g. `http://192.168.0.101:8765`

## Prerequisites

1. **Node.js 20+** (already used for this scaffold)
2. **JDK 17** + **Android Studio** (Ladybug or newer) with Android SDK 35
3. PC and phone on the same Wi‑Fi (or Tailscale)
4. PC brain running:

```bash
python scripts/serve_pwa.py --host 0.0.0.0 --port 8765
```

## Build via GitHub Actions (no local Android Studio)

This repo’s workflow [`.github/workflows/build-apk.yml`](../.github/workflows/build-apk.yml) builds the Capacitor debug APK on push to `main`/`master` (when `mobile/` or `web/` change) or via **Actions → Build Capacitor Android APK → Run workflow**.

1. Push this branch / merge to `main`
2. Open **Actions** on GitHub → run **Build Capacitor Android APK**
3. Download artifact **`universal-soul-companion-debug-apk`**
4. Install the APK on your phone (allow unknown sources)

## Build locally (debug APK)

```bash
cd mobile
npm install
npm run sync-www
npx cap sync android
npx cap open android
```

In Android Studio:

1. Wait for Gradle sync
2. Connect a phone (USB debugging) or start an emulator
3. Run ▸ **app**
4. Or **Build → Build Bundle(s) / APK(s) → Build APK(s)**

APK output (typical):

`mobile/android/app/build/outputs/apk/debug/app-debug.apk`

## First launch on phone

1. Open **Universal Soul**
2. Settings → Connection → set **PC brain URL** to your LAN address  
   (see the PC console: `Phone (Wi-Fi): http://192.168.x.x:8765/`)
3. Save → Test connection
4. Long-press home screen → Widgets → **Universal Soul** companion face

## Sync web UI after changes

Whenever you change `web/`:

```bash
cd mobile
npm run cap:sync
```

Then rebuild/run from Android Studio.

## Notes

- Cleartext HTTP to the LAN PC is intentionally allowed (local-first).
- Voice clone / TTS still run on the **PC**; the phone is the thin client.
- Celebrity voice cloning is not supported — use your own sample + Storyteller.
- Full offline on-device GGUF is a later milestone; this shell needs the PC brain.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Blank / API errors in APK | Set Brain URL; confirm PC `--host 0.0.0.0` |
| Widget stuck on idle | Open the app once so presence syncs |
| Gradle / JDK errors | Install JDK 17 and Android Studio SDK |
| `cap open` fails | Open `mobile/android` folder manually in Android Studio |
