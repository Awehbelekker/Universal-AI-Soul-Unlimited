# Universal AI Soul Unlimited - Complete Setup Guide
## From Consolidation to APK Build

**Date:** October 28, 2025  
**Version:** 1.0.0  
**Status:** Production Ready

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Project Consolidation](#project-consolidation)
3. [CPT-OSS 20B Integration](#cpt-oss-20b-integration)
4. [Configuration](#configuration)
5. [Building the APK](#building-the-apk)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## 1. Prerequisites

### System Requirements

**For Development:**
- Python 3.11+
- 16GB+ RAM recommended
- 50GB+ free disk space
- Windows, macOS, or Linux

**For APK Building:**
- Buildozer
- Android SDK
- Android NDK 25b
- Java JDK 11+

### Install Python Dependencies

```bash
pip install buildozer cython
```

---

## 2. Project Consolidation

### Step 1: Run Consolidation Script

```bash
cd "C:\Users\Richard.Downing\OneDrive - ITEC Group\Desktop\Universal-Soul-AI-Complete"

python consolidate_projects.py
```

**What this does:**
- Merges Universal-Soul-AI-Complete and Soul Project
- Creates "Universal AI Soul Unlimited" folder
- Combines all thinkmesh_core modules
- Merges models and checkpoints
- Integrates android_overlay components
- Generates consolidation report

### Step 2: Verify Consolidation

```bash
cd "..\Universal AI Soul Unlimited"

# Check the consolidation report
type consolidation_report.json

# Check the summary
type CONSOLIDATION_SUMMARY.md
```

### Step 3: Review Duplicate Files

If the consolidation report shows duplicate files, review them manually:

```bash
# Open the report in your editor
code consolidation_report.json
```

Look for the `duplicate_files` section and verify that the correct versions were kept.

---

## 3. CPT-OSS 20B Integration

### Step 1: Install Dependencies

```bash
pip install llama-cpp-python psutil huggingface-hub
```

**Note:** For Windows, you may need to install Visual Studio Build Tools first.

### Step 2: Download CPT-OSS 20B Model

Choose the quantization level based on your target devices:

**Q4 Quantization (Recommended)** - ~10GB RAM required
```bash
huggingface-cli download TheBloke/CPT-OSS-20B-GGUF cpt-oss-20b.Q4_K_M.gguf --local-dir models/
```

**Q8 Quantization (High-End Devices)** - ~20GB RAM required
```bash
huggingface-cli download TheBloke/CPT-OSS-20B-GGUF cpt-oss-20b.Q8_0.gguf --local-dir models/
```

### Step 3: Test CPT-OSS Integration

```bash
python thinkmesh_core\localai\cpt_oss_integration.py
```

Expected output:
```
Testing CPT-OSS 20B Integration...
Device capabilities detected:
  RAM: 15.8GB / 16.0GB
  CPU Cores: 8
  GPU: False
  Storage: 120.5GB
  Platform: Windows
  Mobile: False
Device supports ADVANCED tier (CPT-OSS 20B Q4)

Model Info:
  Tier: advanced
  Model: cpt-oss-20b-q4
  Loaded: True
```

---

## 4. Configuration

### Step 1: Update config/config.json

```json
{
  "app": {
    "name": "Universal AI Soul Unlimited",
    "version": "1.0.0",
    "debug": false
  },
  "hrm": {
    "backend": "ollama",
    "model": "qwen2.5:3b",
    "personality_mode": "friendly",
    "fallback_enabled": true
  },
  "localai": {
    "enabled": true,
    "default_model": "qwen2.5-3b",
    "cpt_oss_enabled": true,
    "cpt_oss_auto_select": true
  },
  "voice": {
    "enabled": true,
    "stt_provider": "deepgram",
    "tts_provider": "elevenlabs",
    "fallback_to_local": true,
    "api_keys": {
      "deepgram": "YOUR_DEEPGRAM_API_KEY",
      "elevenlabs": "YOUR_ELEVENLABS_API_KEY"
    }
  },
  "privacy": {
    "local_only": true,
    "encryption_enabled": true,
    "telemetry_disabled": true,
    "cloud_sync": false
  },
  "orchestration": {
    "max_agents": 5,
    "collective_intelligence": true,
    "default_strategy": "collaborative"
  }
}
```

### Step 2: Update buildozer.spec

The buildozer.spec file has already been updated with:
- ✅ All required dependencies
- ✅ All necessary permissions
- ✅ Updated API levels (33/24)
- ✅ NDK 25b
- ✅ Multi-architecture support (arm64-v8a, armeabi-v7a)

---

## 5. Building the APK

### Step 1: Clean Previous Builds (Optional)

```bash
buildozer android clean
```

### Step 2: Build Debug APK

```bash
buildozer -v android debug
```

**Expected build time:**
- First build: 30-60 minutes
- Subsequent builds: 5-15 minutes

### Step 3: Locate the APK

The APK will be in:
```
bin/universalsoulai-1.0.0-arm64-v8a-debug.apk
bin/universalsoulai-1.0.0-armeabi-v7a-debug.apk
```

### Step 4: Build Release APK (Optional)

For production release:

```bash
# First, create a signing key
keytool -genkey -v -keystore universalsoul.keystore -alias universalsoul -keyalg RSA -keysize 2048 -validity 10000

# Then build release
buildozer -v android release
```

---

## 6. Testing

### Step 1: Install on Device

```bash
# Using ADB
adb install -r bin/universalsoulai-1.0.0-arm64-v8a-debug.apk

# Or transfer to device and install manually
```

### Step 2: Grant Permissions

On first launch, grant the following permissions:
- ✅ Microphone (for voice)
- ✅ Storage (for models and data)
- ✅ Accessibility (for automation)
- ✅ Overlay (for system overlay)

### Step 3: Test Core Features

**Voice Test:**
1. Tap the microphone icon
2. Say "Hello, how are you?"
3. Verify voice recognition and response

**AI Test:**
1. Type: "Explain quantum computing"
2. Verify AI response quality
3. Check response time

**Automation Test:**
1. Enable overlay
2. Use gesture navigation
3. Test context-aware automation

**Privacy Test:**
1. Enable airplane mode
2. Verify app works offline
3. Check privacy indicators

---

## 7. Troubleshooting

### Build Errors

**Error: "NDK not found"**
```bash
buildozer android update
```

**Error: "SDK license not accepted"**
```bash
# Edit buildozer.spec
android.accept_sdk_license = True
```

**Error: "Python 3.11 not found"**
```bash
# Update buildozer.spec
requirements = python3==3.11,...
```

### Runtime Errors

**Error: "Model not found"**
- Ensure models are in the `models/` directory
- Check model paths in config

**Error: "Permission denied"**
- Grant all required permissions in Android settings
- Check app permissions in Settings > Apps

**Error: "Voice not working"**
- Check microphone permission
- Verify API keys in config
- Test with fallback to local mode

### Performance Issues

**Slow AI responses:**
- Check device RAM and CPU
- Verify correct model tier is selected
- Enable battery optimization exceptions

**High battery drain:**
- Check if heavy model is running
- Verify battery-aware mode is enabled
- Review background processes

---

## 📊 Feature Checklist

Before releasing to users, verify:

- [ ] Project consolidated successfully
- [ ] CPT-OSS 20B integrated (optional)
- [ ] Configuration updated
- [ ] APK builds without errors
- [ ] App installs on device
- [ ] Voice recognition works
- [ ] Voice synthesis works
- [ ] AI responses are accurate
- [ ] Automation works
- [ ] Privacy mode verified
- [ ] Offline mode works
- [ ] Multi-agent orchestration functional
- [ ] Android overlay displays correctly
- [ ] Battery usage acceptable
- [ ] Performance acceptable

---

## 🎯 Next Steps

1. **User Testing**
   - Deploy to test users
   - Collect feedback
   - Monitor crash reports

2. **Optimization**
   - Profile performance
   - Optimize model loading
   - Reduce APK size

3. **Documentation**
   - Create user manual
   - Document API endpoints
   - Write developer guide

4. **Marketing**
   - Prepare app store listing
   - Create promotional materials
   - Plan launch strategy

---

## 📞 Support

For issues or questions:
- GitHub: https://github.com/Awehbelekker/universal-soul-ai
- Documentation: [Link to docs]
- Community: [Link to Discord/Forum]

---

**Universal AI Soul Unlimited** - The future of local AI is here! 🚀
