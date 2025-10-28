# Universal Soul AI - Android Build Quick Start

## Prerequisites

1. **Install Buildozer** (on Linux/Mac/WSL):
   ```bash
   pip install buildozer
   ```

2. **Install Build Dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install -y git zip unzip openjdk-11-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
   
   # Fedora
   sudo dnf install -y git zip unzip java-11-openjdk-devel python3-pip autoconf libtool pkg-config zlib-devel ncurses-devel cmake libffi-devel openssl-devel
   ```

## Quick Build

### Option 1: Using Build Script (Recommended)
```bash
python build_android.py
```

Then select:
- Option 1: Build Debug APK (for testing)
- Option 2: Build Release APK (for production)
- Option 3: Deploy to device

### Option 2: Direct Buildozer Commands

**Debug Build** (for testing):
```bash
buildozer android debug
```

**Release Build** (for production):
```bash
buildozer android release
```

**Deploy to Device**:
```bash
buildozer android deploy run
```

## Build Output

APK will be created in:
```
bin/universalsoulai-1.0.0-debug.apk    (debug build)
bin/universalsoulai-1.0.0-release.apk  (release build)
```

## Build Size

- **Lightweight Build**: ~250MB
  - Includes placeholder 27M model
  - Optional Qwen2.5-3B download in-app
  
- **Full Build**: ~2.5GB
  - Includes Qwen2.5-3B model
  - No additional downloads needed

## Testing

1. **Install on Device**:
   ```bash
   adb install bin/universalsoulai-*.apk
   ```

2. **Run App**:
   - Launch "Universal Soul AI" from app drawer
   - Test basic chat functionality
   - Go to Settings → Link Advanced AI (if lightweight build)

## Troubleshooting

### Build Fails
- Clean build: `buildozer android clean`
- Check Java version: `java -version` (need 11+)
- Verify Android SDK/NDK installed

### APK Too Large
- Use lightweight build (default)
- Remove unnecessary assets from source.include_exts
- Check models/ directory size

### Device Connection Issues
- Enable USB debugging on device
- Authorize computer on device
- Check: `adb devices`

## Production Release

1. **Create Keystore** (first time only):
   ```bash
   keytool -genkey -v -keystore universal-soul.keystore -alias universalsoul -keyalg RSA -keysize 2048 -validity 10000
   ```

2. **Sign APK**:
   ```bash
   jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 -keystore universal-soul.keystore bin/universalsoulai-1.0.0-release-unsigned.apk universalsoul
   ```

3. **Align APK**:
   ```bash
   zipalign -v 4 bin/universalsoulai-1.0.0-release-unsigned.apk bin/universalsoulai-1.0.0-release.apk
   ```

4. **Upload to Play Store**

## Next Steps

After successful build:
1. ✓ Test on multiple Android devices
2. ✓ Verify all AI features work
3. ✓ Test model download/linking flow
4. ✓ Performance testing
5. ✓ Submit to Play Store

---

**Need Help?** Check ANDROID_BUILD_GUIDE.md for detailed documentation.
