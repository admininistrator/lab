param(
    [string]$Namespace = "bd-g06",
    [string]$OutFile,
    [string]$StopFile,
    [int]$IntervalSeconds = 5
)

$ErrorActionPreference = "Continue"

function Write-Sample {
    param([string]$Text)
    $stamp = (Get-Date).ToUniversalTime().ToString("o")
    Add-Content -Path $OutFile -Value ("=== $stamp ===")
    Add-Content -Path $OutFile -Value $Text
    Add-Content -Path $OutFile -Value ""
}

while (-not (Test-Path $StopFile)) {
    $podsNs = kubectl -n $Namespace get pods -o wide 2>&1 | Out-String
    $topNs = kubectl -n $Namespace top pod 2>&1 | Out-String
    $podsAll = kubectl get pods -A -o wide 2>&1 | Out-String
    $topAll = kubectl top pod -A 2>&1 | Out-String
    $nodes = kubectl get nodes -o wide 2>&1 | Out-String

    Write-Sample @"
[namespace pods]
$podsNs
[namespace top]
$topNs
[cluster pods]
$podsAll
[cluster top]
$topAll
[nodes]
$nodes
"@

    Start-Sleep -Seconds $IntervalSeconds
}
