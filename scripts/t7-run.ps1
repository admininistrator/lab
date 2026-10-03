param(
    [string]$Namespace = "bd-g06"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Error "kubectl was not found. Run this on the PC with Docker Desktop Kubernetes."
}

$Evidence = Join-Path $RepoRoot "evidence\t7"
New-Item -ItemType Directory -Force -Path $Evidence | Out-Null

$StopFile = Join-Path $Evidence "STOP_SAMPLING"
if (Test-Path $StopFile) { Remove-Item $StopFile -Force }

Write-Host "==> Placement and baseline (do not change resources between trials)"
kubectl config current-context | Out-File (Join-Path $Evidence "environment.txt")
kubectl -n $Namespace get pods -o wide | Out-File (Join-Path $Evidence "placement.txt")
kubectl -n $Namespace get deploy,svc,pvc | Out-File (Join-Path $Evidence "resources.txt")
kubectl get pods -A -o wide | Out-File (Join-Path $Evidence "cluster-activity-before.txt")
kubectl get nodes -o wide | Out-File (Join-Path $Evidence "nodes.txt")

$ingestor = kubectl -n $Namespace get pod ingestor -o json | ConvertFrom-Json
if ($ingestor.status.phase -ne "Running") {
    Write-Error "ingestor is not Running"
}

Write-Host "==> Starting 5s sampler (kubectl top + pod status)"
$sampleOut = Join-Path $Evidence "samples.txt"
$sampleScript = Join-Path $PSScriptRoot "t7-sample.ps1"
$sampler = Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-File", $sampleScript,
    "-Namespace", $Namespace,
    "-OutFile", $sampleOut,
    "-StopFile", $StopFile,
    "-IntervalSeconds", "5"
) -PassThru -WindowStyle Hidden

try {
    function Write-Utf8 {
        param([string]$Path, [string[]]$Lines)
        $text = ($Lines -join "`n") + "`n"
        [System.IO.File]::WriteAllText($Path, $text, [System.Text.UTF8Encoding]::new($false))
    }

    Write-Host "==> Warm-up GET (excluded from measured trials)"
    $warmup = kubectl -n $Namespace exec ingestor -- python /opt/s3lab.py probe get research-raw fixture.txt
    Write-Utf8 (Join-Path $Evidence "warmup.jsonl") @($warmup)

    $pairs = @(
        @{ C = "1"; Prefix = "r1-c1" },
        @{ C = "4"; Prefix = "r1-c4" },
        @{ C = "4"; Prefix = "r2-c4" },
        @{ C = "1"; Prefix = "r2-c1" },
        @{ C = "1"; Prefix = "r3-c1" },
        @{ C = "4"; Prefix = "r3-c4" }
    )

    foreach ($pair in $pairs) {
        $out = Join-Path $Evidence "$($pair.Prefix).jsonl"
        Write-Host "==> Trial concurrency=$($pair.C) prefix=bench/$($pair.Prefix)"
        $lines = kubectl -n $Namespace exec ingestor -- python /opt/s3lab.py bench $pair.C "bench/$($pair.Prefix)"
        Write-Utf8 $out @($lines)
    }
}
finally {
    New-Item -ItemType File -Force -Path $StopFile | Out-Null
    if ($sampler -and -not $sampler.HasExited) {
        Wait-Process -Id $sampler.Id -Timeout 12 -ErrorAction SilentlyContinue
        if (-not $sampler.HasExited) {
            Stop-Process -Id $sampler.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

kubectl get pods -A -o wide | Out-File (Join-Path $Evidence "cluster-activity-after.txt")

Write-Host "==> Analyzing JSONL"
python (Join-Path $PSScriptRoot "t7-analyze.py") $Evidence

Write-Host ""
Write-Host "Evidence directory: $Evidence"
Write-Host "Report: $(Join-Path $Evidence 'REPORT.md')"
