# 🚀 Qwen2.5-3B Setup & Optimization - Quick Start

## Step 1: Setup Ollama (One-Time)

Ollama is installed but not in your PATH. Choose one option:

### Option A: Add Ollama to PATH (Recommended)

```powershell
# Add Ollama to your PATH permanently
$ollamaPath = "$env:LOCALAPPDATA\Programs\Ollama"
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$ollamaPath*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$ollamaPath", "User")
    Write-Host "✅ Ollama added to PATH. Please restart your terminal."
}

# For current session only (temporary)
$env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"
```

### Option B: Use Full Path (Quick)

```powershell
# Create an alias for this session
Set-Alias -Name ollama -Value "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
```

---

## Step 2: Start Ollama Service

```powershell
# Start Ollama server (keep this terminal open)
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" -ArgumentList "serve"

# Or in current terminal (will block)
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve
```

---

## Step 3: Verify Ollama is Running

Open a **new terminal** and run:

```powershell
# Test Ollama
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list

# Or if you added to PATH:
ollama list
```

---

## Step 4: Download Qwen2.5-3B

```powershell
# Download the base model
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull qwen2.5:3b

# This will take a few minutes (downloads ~2GB)
```

---

## Step 5: Run Optimization

Now you can run the optimization script:

```powershell
# Option 1: Run the automated wizard
.\optimize_qwen_fixed.ps1

# Option 2: Quick manual test
python test_qwen_quick.py

# Option 3: Full benchmark
python benchmark_qwen_performance.py
```

---

## Quick Commands Reference

```powershell
# Set path for current session
$env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"

# Check if Ollama is running
Invoke-WebRequest -Uri "http://localhost:11434" -UseBasicParsing

# List installed models
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list

# Test a model
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" run qwen2.5:3b "Hello!"

# Stop Ollama (if needed)
Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue
```

---

## Troubleshooting

### "Ollama not found"
- Ollama is at: `%LOCALAPPDATA%\Programs\Ollama\ollama.exe`
- Add to PATH or use full path
- Restart terminal after adding to PATH

### "Connection refused"
- Start Ollama server: `ollama serve`
- Check if running: `Get-Process ollama`

### "Model not found"
- Download model: `ollama pull qwen2.5:3b`
- List models: `ollama list`

---

## Complete Setup Script (Copy & Paste)

```powershell
# 1. Add Ollama to PATH for current session
$env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"

# 2. Start Ollama service in background
Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden

# 3. Wait for service to start
Start-Sleep -Seconds 3

# 4. Download Qwen2.5-3B (if not already downloaded)
ollama pull qwen2.5:3b

# 5. Test it
ollama run qwen2.5:3b "Hello! Test message."

# 6. Run optimization
.\optimize_qwen_fixed.ps1
```

---

## Next Steps After Setup

1. **Create Optimized Model**
   ```powershell
   ollama create qwen2.5-optimized -f Modelfile
   ```

2. **Run Benchmark**
   ```powershell
   python benchmark_qwen_performance.py
   ```

3. **Update Your App**
   - Change model to `qwen2.5-optimized` in config
   - See `QWEN2.5_OPTIMIZATION_GUIDE.md`

---

**Ready?** Run the complete setup script above, then proceed with optimization! 🚀
