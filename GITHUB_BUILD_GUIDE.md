# Universal Soul AI - GitHub APK builds

Use **GitHub Actions** to produce the Capacitor companion APK without a local Android Studio install.

## Capacitor APK (current)

Workflow: `.github/workflows/build-apk.yml`

1. Push to `main` / `master`, or open **Actions → Build Capacitor Android APK → Run workflow**
2. Download artifact **`universal-soul-companion-debug-apk`**
3. Install on Android 8+ (allow unknown sources)
4. In the app: Settings → **PC brain URL** → your LAN `http://192.168.x.x:8765`

Details: [docs/MOBILE_APK.md](docs/MOBILE_APK.md)

## Legacy Buildozer / Kivy

Older guides referred to Buildozer. That path is superseded by the Capacitor shell in `mobile/`. Keep `buildozer.spec` only if you still maintain the Kivy beta; new phone installs should use Capacitor.
