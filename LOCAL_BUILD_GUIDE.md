# Local APK Build Instructions

## Option 1: Build Locally with Buildozer (Recommended for Testing)

### Prerequisites

#### Windows (WSL2 Required)
```powershell
# Install WSL2 if not already installed
wsl --install

# Open WSL Ubuntu terminal
wsl
```

#### Inside WSL/Linux/macOS
```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install system dependencies
sudo apt-get install -y \
    git zip unzip openjdk-11-jdk \
    autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 \
    cmake libffi-dev libssl-dev \
    build-essential ccache \
    libltdl-dev python3-dev

# Install Python 3.9
sudo apt-get install -y python3.9 python3.9-dev python3-pip

# Create virtual environment
python3.9 -m venv buildenv
source buildenv/bin/activate

# Install buildozer and dependencies
pip install --upgrade pip setuptools wheel
pip install --upgrade cython==0.29.36
pip install --upgrade buildozer
pip install --upgrade git+https://github.com/kivy/python-for-android.git@develop
```

### Build APK

```bash
# Navigate to project directory
cd "/mnt/c/Users/Richard.Downing/OneDrive - ITEC Group/Desktop/Universal AI Soul Unlimited"

# First build (will take 30-60 minutes)
buildozer android debug

# Subsequent builds (much faster with cache)
buildozer android debug

# Build release version (for distribution)
buildozer android release
```

### Find Your APK

```bash
# Debug APK location
ls -lh ./bin/*.apk

# Copy to Windows desktop
cp ./bin/*.apk /mnt/c/Users/Richard.Downing/Desktop/
```

### Transfer to Android Device

1. **USB Transfer**: Connect phone via USB and copy APK
2. **Cloud**: Upload to Google Drive/Dropbox and download on phone
3. **ADB**: 
   ```bash
   # Install on connected device
   adb install ./bin/universalaisoul-0.1-arm64-v8a-debug.apk
   ```

---

## Option 2: Docker Build (Fastest After Setup)

### Prerequisites
- Docker Desktop installed on Windows

### Build Script

Save as `build_with_docker.ps1`:

```powershell
# Build APK using Docker
docker run --rm -v "${PWD}:/app" \
    kivy/buildozer android debug

# APK will be in ./bin/ folder
```

Run:
```powershell
cd "C:\Users\Richard.Downing\OneDrive - ITEC Group\Desktop\Universal AI Soul Unlimited"
.\build_with_docker.ps1
```

---

## Option 3: Alternative CI/CD Services

### GitHub Actions Alternatives

1. **GitLab CI/CD** (Free tier: 400 minutes/month)
   - Faster runner allocation
   - Better free tier limits
   - Add `.gitlab-ci.yml`:
   ```yaml
   build-apk:
     image: python:3.9
     script:
       - apt-get update && apt-get install -y openjdk-11-jdk
       - pip install buildozer
       - buildozer android debug
     artifacts:
       paths:
         - bin/*.apk
   ```

2. **CircleCI** (Free tier: 6,000 minutes/month)
   - Add `.circleci/config.yml`
   - Faster builds than GitHub Actions

3. **Travis CI** (Free for open source)
   - Add `.travis.yml`

---

## Troubleshooting

### Common Issues

**Build fails with NDK error:**
```bash
# Specify NDK version in buildozer.spec
android.ndk = 25c
```

**Out of memory:**
```bash
# Add swap space
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**Permission denied:**
```bash
# Fix permissions
chmod +x buildozer
chmod -R 755 ~/.buildozer
```

### Speed Up Builds

1. **Use ccache:**
   ```bash
   export USE_CCACHE=1
   export CCACHE_DIR=$HOME/.ccache
   ```

2. **Keep buildozer cache:**
   - Don't delete `.buildozer` folder between builds
   - First build: 30-60 min
   - Subsequent builds: 5-15 min

3. **Build in parallel:**
   ```bash
   # Use all CPU cores
   buildozer -v android debug
   ```

---

## Quick Start (Copy-Paste)

```bash
# WSL setup and build (one command)
wsl bash -c "cd '/mnt/c/Users/Richard.Downing/OneDrive - ITEC Group/Desktop/Universal AI Soul Unlimited' && \
sudo apt-get install -y python3.9 python3-pip openjdk-11-jdk build-essential && \
pip3 install buildozer && \
buildozer android debug && \
cp ./bin/*.apk /mnt/c/Users/Richard.Downing/Desktop/"
```

APK will be on your Desktop!

---

## Build Status Check

While waiting for GitHub Actions:
```bash
# Check build status
python quick_status.py

# Continuous monitoring
python continuous_monitor.py

# Analyze failures
python analyze_build.py latest
```
