# Ready the PC for phone PWA testing (firewall + LAN URL).
#   powershell -ExecutionPolicy Bypass -File scripts\ready_pwa_lan.ps1

$ErrorActionPreference = "Continue"
$Port = 8765

Write-Host "Universal Soul - PWA LAN ready check" -ForegroundColor Cyan

$ruleName = "UniversalSoul-PWA-$Port"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if (-not $existing) {
    try {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Private,Domain | Out-Null
        Write-Host "Firewall: allowed TCP $Port (Private/Domain)" -ForegroundColor Green
    } catch {
        Write-Host "Firewall: could not add rule (run as Admin): $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "Firewall: rule already present ($ruleName)" -ForegroundColor Green
}

$ips = Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
    Select-Object -ExpandProperty IPAddress -Unique

Write-Host ""
Write-Host "On this PC open:  http://127.0.0.1:$Port/"
foreach ($ip in $ips) {
    Write-Host "On your phone:    http://${ip}:$Port/"
}

Write-Host ""
Write-Host "Step 1 - Keep Ollama running on this PC"
Write-Host "Step 2 - Start server:  python scripts/serve_pwa.py"
Write-Host "Step 3 - Phone same Wi-Fi, open URL, Settings, Test, chat"
Write-Host "Step 4 - Chrome/Edge menu: Add to Home Screen / Install app"
Write-Host ""
Write-Host "If Test fails from phone, keep Ollama URL as http://127.0.0.1:11434"
Write-Host "because the PWA proxies through this PC on port $Port."
