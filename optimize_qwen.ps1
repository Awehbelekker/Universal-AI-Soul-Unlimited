# Qwen2.5-3B Optimization Script for Windows
# This script applies optimizations to your Ollama setup

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Qwen2.5-3B Optimization Wizard" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check if Ollama is installed
Write-Host "Checking Ollama installation..." -ForegroundColor Yellow
$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaPath) {
    Write-Host "❌ Ollama not found. Please install from: https://ollama.ai" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Ollama found at: $($ollamaPath.Source)" -ForegroundColor Green

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
$models = ollama list 2>$null | Select-String "qwen2.5"

if ($models) {
    Write-Host "✅ Qwen2.5 models found:" -ForegroundColor Green
    $models | ForEach-Object { Write-Host "  $_" -ForegroundColor Cyan }
} else {
    Write-Host "⚠️  Qwen2.5-3B not found" -ForegroundColor Yellow
    $download = Read-Host "Download qwen2.5:3b now? (y/n)"
    if ($download -eq 'y') {
        Write-Host "Downloading qwen2.5:3b (this may take a few minutes)..." -ForegroundColor Yellow
        ollama pull qwen2.5:3b
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
    ollama create qwen2.5-optimized -f $modelfilePath
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
    
    $config = Get-Content $configPath | ConvertFrom-Json
    $config.hrm.ollama_model = "qwen2.5-optimized"
    $config.ollama.gpu_enabled = $hasGPU
    
    $config | ConvertTo-Json -Depth 10 | Set-Content $configPath
    Write-Host "✅ Configuration updated" -ForegroundColor Green
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
    ollama run qwen2.5-optimized $testPrompt
    $endTime = Get-Date
    
    $duration = ($endTime - $startTime).TotalSeconds
    Write-Host "`n⏱️  Response time: $([math]::Round($duration, 2)) seconds" -ForegroundColor Cyan
}

# Run benchmark
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Performance Benchmark" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$runBenchmark = Read-Host "Run full performance benchmark? (y/n)"
if ($runBenchmark -eq 'y') {
    if (Test-Path "benchmark_qwen_performance.py") {
        Write-Host "Starting benchmark..." -ForegroundColor Yellow
        python benchmark_qwen_performance.py
    } else {
        Write-Host "❌ Benchmark script not found: benchmark_qwen_performance.py" -ForegroundColor Red
    }
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Optimization Complete!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Restart Ollama service: Stop-Process -Name ollama; ollama serve" -ForegroundColor Cyan
Write-Host "  2. Test the optimized model: ollama run qwen2.5-optimized" -ForegroundColor Cyan
Write-Host "  3. Run benchmark: python benchmark_qwen_performance.py" -ForegroundColor Cyan
Write-Host "  4. Review guide: QWEN2.5_OPTIMIZATION_GUIDE.md`n" -ForegroundColor Cyan

Write-Host "Performance Tips:" -ForegroundColor Yellow
Write-Host "  • Use GPU acceleration for 2-5x speedup" -ForegroundColor Cyan
Write-Host "  • Enable caching for common queries" -ForegroundColor Cyan
Write-Host "  • Use streaming for better user experience" -ForegroundColor Cyan
Write-Host "  • Monitor performance with benchmarks`n" -ForegroundColor Cyan

Write-Host "For detailed optimization strategies, see:" -ForegroundColor Yellow
Write-Host "  QWEN2.5_OPTIMIZATION_GUIDE.md`n" -ForegroundColor Cyan

Write-Host "Optimization wizard complete! 🚀`n" -ForegroundColor Green
