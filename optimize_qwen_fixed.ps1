# Qwen2.5-3B Optimization Script for Windows (Fixed)
# Handles Ollama path issues automatically

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Qwen2.5-3B Optimization Wizard" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Function to find Ollama
function Find-Ollama {
    # Check common locations
    $locations = @(
        (Get-Command ollama -ErrorAction SilentlyContinue),
        "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
        "$env:ProgramFiles\Ollama\ollama.exe",
        "C:\Program Files\Ollama\ollama.exe"
    )
    
    foreach ($loc in $locations) {
        if ($loc) {
            if ($loc.Source) { return $loc.Source }
            if (Test-Path $loc) { return $loc }
        }
    }
    
    return $null
}

# Find Ollama installation
Write-Host "Checking Ollama installation..." -ForegroundColor Yellow
$ollamaExe = Find-Ollama

if (-not $ollamaExe) {
    Write-Host "❌ Ollama not found." -ForegroundColor Red
    Write-Host "`nPlease install Ollama from: https://ollama.ai" -ForegroundColor Yellow
    Write-Host "`nOr if already installed, see SETUP_QWEN.md for setup instructions." -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Ollama found at: $ollamaExe" -ForegroundColor Green

# Add to PATH for this session if needed
$ollamaDir = Split-Path -Parent $ollamaExe
if ($env:Path -notlike "*$ollamaDir*") {
    $env:Path += ";$ollamaDir"
    Write-Host "✅ Ollama added to PATH for this session" -ForegroundColor Green
}

# Check if Ollama service is running
Write-Host "`nChecking Ollama service..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:11434" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    Write-Host "✅ Ollama service is running" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Ollama service not running" -ForegroundColor Yellow
    Write-Host "Starting Ollama service..." -ForegroundColor Yellow
    Start-Process $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
    Write-Host "✅ Ollama service started (running in background)" -ForegroundColor Green
    Start-Sleep -Seconds 3
}

# Get system information
Write-Host "`nGathering system information..." -ForegroundColor Yellow

$cpuCores = (Get-WmiObject Win32_Processor).NumberOfLogicalProcessors
$totalRAM = [math]::Round((Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)

Write-Host "  CPU Cores: $cpuCores" -ForegroundColor Cyan
Write-Host "  Total RAM: $totalRAM GB" -ForegroundColor Cyan

# Check for NVIDIA GPU
$hasGPU = $false
$gpuMemory = 0
try {
    $nvidiaSmi = nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null
    if ($nvidiaSmi) {
        $hasGPU = $true
        $gpuMemory = [int]$nvidiaSmi / 1024
        Write-Host "  GPU: NVIDIA (${gpuMemory}GB VRAM)" -ForegroundColor Cyan
    }
} catch {
    Write-Host "  GPU: None detected" -ForegroundColor Cyan
}

# Recommend settings
Write-Host "`nRecommended Settings:" -ForegroundColor Yellow

$recommendedThreads = [math]::Floor($cpuCores * 0.75)
$recommendedGPU = 0
$recommendedQuant = "q4"

if ($hasGPU) {
    if ($gpuMemory -ge 12) {
        $recommendedGPU = 35
        $recommendedQuant = "q8"
        Write-Host "  🚀 Full GPU acceleration (num_gpu: 35)" -ForegroundColor Green
    } elseif ($gpuMemory -ge 8) {
        $recommendedGPU = 25
        $recommendedQuant = "q5"
        Write-Host "  ⚡ Partial GPU acceleration (num_gpu: 25)" -ForegroundColor Green
    } else {
        $recommendedGPU = 15
        Write-Host "  💡 Limited GPU acceleration (num_gpu: 15)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  💻 CPU-only mode (num_gpu: 0)" -ForegroundColor Yellow
}

Write-Host "  Threads: $recommendedThreads" -ForegroundColor Cyan
Write-Host "  Quantization: $recommendedQuant" -ForegroundColor Cyan

# Set environment variables
Write-Host "`nConfiguring Ollama environment..." -ForegroundColor Yellow

$envVars = @{
    'OLLAMA_NUM_PARALLEL' = '2'
    'OLLAMA_MAX_LOADED_MODELS' = '2'
    'OLLAMA_KEEP_ALIVE' = '5m'
    'OLLAMA_HOST' = '0.0.0.0:11434'
}

foreach ($var in $envVars.GetEnumerator()) {
    [System.Environment]::SetEnvironmentVariable($var.Key, $var.Value, 'User')
    Write-Host "  Set $($var.Key) = $($var.Value)" -ForegroundColor Cyan
}

Write-Host "✅ Environment variables configured" -ForegroundColor Green

# Check if qwen2.5:3b is available
Write-Host "`nChecking for Qwen2.5-3B model..." -ForegroundColor Yellow
$models = & $ollamaExe list 2>$null | Select-String "qwen2.5"

if ($models) {
    Write-Host "✅ Qwen2.5 models found:" -ForegroundColor Green
    $models | ForEach-Object { Write-Host "  $_" -ForegroundColor Cyan }
} else {
    Write-Host "⚠️  Qwen2.5-3B not found" -ForegroundColor Yellow
    $download = Read-Host "Download qwen2.5:3b now? (y/n)"
    if ($download -eq 'y') {
        Write-Host "Downloading qwen2.5:3b (this may take a few minutes)..." -ForegroundColor Yellow
        & $ollamaExe pull qwen2.5:3b
    } else {
        Write-Host "⚠️  Skipping optimization without base model" -ForegroundColor Yellow
        exit 0
    }
}

# Create optimized Modelfile
Write-Host "`nCreating optimized Modelfile..." -ForegroundColor Yellow

$modelfileContent = @"
FROM qwen2.5:3b

# Performance Parameters
PARAMETER num_ctx 32768
PARAMETER num_thread $recommendedThreads
PARAMETER num_gpu $recommendedGPU
PARAMETER num_batch 512
PARAMETER num_keep 4

# Quality Parameters
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER repeat_penalty 1.1
PARAMETER repeat_last_n 64

# Advanced Sampling
PARAMETER mirostat 2
PARAMETER mirostat_tau 5.0
PARAMETER mirostat_eta 0.1

# Generation Limits
PARAMETER num_predict 2048
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"

# System Prompt
SYSTEM """You are Universal Soul AI, an intelligent and helpful AI assistant. Respond clearly and concisely."""
"@

$modelfilePath = Join-Path $PWD "Modelfile.optimized"
$modelfileContent | Out-File -FilePath $modelfilePath -Encoding UTF8
Write-Host "✅ Modelfile created: $modelfilePath" -ForegroundColor Green

# Create optimized model
Write-Host "`nCreating optimized model variant..." -ForegroundColor Yellow
$createModel = Read-Host "Create 'qwen2.5-optimized' model? (y/n)"

if ($createModel -eq 'y') {
    Write-Host "Creating model (this may take a minute)..." -ForegroundColor Yellow
    & $ollamaExe create qwen2.5-optimized -f $modelfilePath
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Model 'qwen2.5-optimized' created successfully!" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to create optimized model" -ForegroundColor Red
    }
}

# Update configuration file
$configPath = "config\universal_soul.json"
if (Test-Path $configPath) {
    Write-Host "`nUpdating configuration file..." -ForegroundColor Yellow
    
    try {
        $config = Get-Content $configPath | ConvertFrom-Json
        $config.hrm.ollama_model = "qwen2.5-optimized"
        $config.ollama.gpu_enabled = $hasGPU
        
        $config | ConvertTo-Json -Depth 10 | Set-Content $configPath
        Write-Host "✅ Configuration updated" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  Could not update configuration: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  Configuration file not found at: $configPath" -ForegroundColor Yellow
}

# Test the optimized model
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Testing Optimized Model" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$testModel = Read-Host "Test qwen2.5-optimized now? (y/n)"
if ($testModel -eq 'y') {
    Write-Host "`nRunning test query..." -ForegroundColor Yellow
    $testPrompt = "Explain artificial intelligence in 2 sentences."
    
    $startTime = Get-Date
    & $ollamaExe run qwen2.5-optimized $testPrompt
    $endTime = Get-Date
    
    $duration = ($endTime - $startTime).TotalSeconds
    Write-Host "`n⏱️  Response time: $([math]::Round($duration, 2)) seconds" -ForegroundColor Cyan
    
    if ($duration -lt 2) {
        Write-Host "✅ Excellent performance!" -ForegroundColor Green
    } elseif ($duration -lt 4) {
        Write-Host "✅ Good performance" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Consider enabling GPU acceleration for better performance" -ForegroundColor Yellow
    }
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Optimization Complete!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "What's Been Done:" -ForegroundColor Yellow
Write-Host "  ✅ Found and configured Ollama" -ForegroundColor Cyan
Write-Host "  ✅ Optimized settings for your system" -ForegroundColor Cyan
Write-Host "  ✅ Created Modelfile.optimized" -ForegroundColor Cyan
if ($createModel -eq 'y') {
    Write-Host "  ✅ Created qwen2.5-optimized model" -ForegroundColor Cyan
}
Write-Host "  ✅ Updated environment variables`n" -ForegroundColor Cyan

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Use the optimized model: ollama run qwen2.5-optimized" -ForegroundColor Cyan
Write-Host "  2. Run benchmark: python benchmark_qwen_performance.py" -ForegroundColor Cyan
Write-Host "  3. Quick test: python test_qwen_quick.py" -ForegroundColor Cyan
Write-Host "  4. Read guide: QWEN2.5_OPTIMIZATION_GUIDE.md`n" -ForegroundColor Cyan

Write-Host "Performance Tips:" -ForegroundColor Yellow
Write-Host "  • Expected: 1-2s response time, 40-80 tokens/sec" -ForegroundColor Cyan
Write-Host "  • For max speed: Use GPU if available" -ForegroundColor Cyan
Write-Host "  • For best quality: Use Q8 quantization" -ForegroundColor Cyan
Write-Host "  • For balance: Current settings (Q5/default)`n" -ForegroundColor Cyan

Write-Host "Ollama Path: $ollamaExe" -ForegroundColor Gray
Write-Host "To run Ollama commands, use: $ollamaExe <command>`n" -ForegroundColor Gray

Write-Host "Optimization wizard complete! 🚀`n" -ForegroundColor Green
