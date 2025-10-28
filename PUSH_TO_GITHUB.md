# 🚀 PUSH TO GITHUB & BUILD APK - Quick Commands

**Copy and paste these commands into PowerShell!**

---

## Step 1: Check Git Status

```powershell
cd "C:\Users\Richard.Downing\OneDrive - ITEC Group\Desktop\Universal-Soul-AI-Complete"
git status
```

---

## Step 2: Add All New Files

```powershell
git add .
git add .github/
```

---

## Step 3: Commit Changes

```powershell
git commit -m "Add GitHub Actions workflow for Android APK build"
```

---

## Step 4: Push to GitHub

```powershell
# If you haven't set remote yet:
git remote add origin https://github.com/Awehbelekker/universal-soul-ai.git

# Push to GitHub (triggers automatic build!)
git push -u origin master
```

**Note**: If prompted for credentials, you may need a Personal Access Token (not password).

---

## Step 5: Watch the Build

1. **Open browser** → https://github.com/Awehbelekker/universal-soul-ai
2. **Click "Actions" tab** (top menu)
3. **Watch build progress** (yellow circle = running, green = success)
4. **Wait ~30-60 minutes** for first build

---

## Step 6: Download APK

After build completes (green checkmark):

1. **Click on the completed workflow** (in Actions tab)
2. **Scroll down to "Artifacts"** section
3. **Click "universal-soul-ai-debug-apk"** to download ZIP
4. **Extract ZIP** → Get your APK file!

---

## Alternative: Manual Trigger Build

If auto-build doesn't start:

1. Go to: https://github.com/Awehbelekker/universal-soul-ai/actions
2. Click "Build Android APK" (left sidebar)
3. Click "Run workflow" (top right)
4. Select: Branch = master, Build type = debug
5. Click "Run workflow" button

---

## Troubleshooting

### "Remote already exists"

```powershell
git remote remove origin
git remote add origin https://github.com/Awehbelekker/universal-soul-ai.git
```

### "Authentication failed"

Create Personal Access Token:
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token
3. Check: repo, workflow
4. Copy token
5. Use token as password when pushing

### "Need to pull first"

```powershell
git pull origin master --allow-unrelated-histories
git push -u origin master
```

---

## Quick Reference

| Action | Command |
|--------|---------|
| Add files | `git add .` |
| Commit | `git commit -m "message"` |
| Push | `git push` |
| Status | `git status` |
| View remote | `git remote -v` |

---

## What Happens Next?

1. ✅ You push code to GitHub
2. ⚙️ GitHub Actions starts building automatically
3. 🏗️ Ubuntu VM downloads Android SDK, compiles APK (~30-60 min)
4. 📦 APK uploaded as artifact
5. ✅ Build completes (green checkmark)
6. 📥 You download APK from Artifacts
7. 📱 Install on Android device
8. 🎉 Done!

---

## After First Build

Next builds are faster (~10-20 minutes) because:
- ✅ Android SDK cached
- ✅ Dependencies cached
- ✅ Only compiles your changes

---

**Ready? Copy and paste Step 1-4 commands now!** 🚀
