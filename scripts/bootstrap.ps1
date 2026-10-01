param(
    [string]$Namespace = "bd-g06"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Fail {
    param([string]$Message)
    Write-Host ""
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}

# Resolve repository root from scripts/bootstrap.ps1
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Step "Checking required commands"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker CLI was not found. Install/start Docker Desktop first."
}
Write-Ok "docker command found"

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Fail "kubectl was not found. Install kubectl or enable the Docker Desktop Kubernetes tooling."
}
Write-Ok "kubectl command found"

Write-Step "Checking Docker Desktop"

try {
    docker info *> $null
} catch {
    Fail "Docker Desktop is not running. Start Docker Desktop and run this script again."
}
Write-Ok "Docker daemon is reachable"

Write-Step "Checking Kubernetes context"

$contexts = @(kubectl config get-contexts -o name 2>$null)

if ($contexts -notcontains "docker-desktop") {
    Write-Host ""
    Write-Host "The 'docker-desktop' Kubernetes context does not exist." -ForegroundColor Yellow
    Write-Host "Open Docker Desktop and create/enable its Kubernetes cluster first:"
    Write-Host "  Docker Desktop -> Kubernetes -> Create/Enable cluster"
    Write-Host ""
    Write-Host "After Kubernetes is Ready, run this script again."
    exit 1
}

$currentContext = kubectl config current-context 2>$null

if ($currentContext -ne "docker-desktop") {
    kubectl config use-context docker-desktop | Out-Host
}
Write-Ok "Using Kubernetes context: docker-desktop"

Write-Step "Checking Kubernetes node readiness"

try {
    kubectl get nodes | Out-Host
} catch {
    Fail "The Docker Desktop Kubernetes API is not reachable."
}

$notReady = kubectl get nodes --no-headers 2>$null |
    Where-Object { $_ -notmatch '\sReady\s' }

if ($notReady) {
    Fail "At least one Kubernetes node is not Ready."
}
Write-Ok "Kubernetes node is Ready"

Write-Step "Ensuring namespace '$Namespace'"

$existingNamespace = kubectl get namespace $Namespace --ignore-not-found -o name

if (-not $existingNamespace) {
    kubectl create namespace $Namespace | Out-Host
    Write-Ok "Namespace '$Namespace' created"
} else {
    Write-Ok "Namespace '$Namespace' already exists"
}

$env:NS = $Namespace

Write-Step "Locating Task 1 guardrails manifest"

$guardrailsPath = Join-Path $RepoRoot "manifests\guardrails.yaml"

if (-not (Test-Path $guardrailsPath)) {
    $fallback = Join-Path $RepoRoot "guardrails.yaml"
    if (Test-Path $fallback) {
        $guardrailsPath = $fallback
    } else {
        Fail "Could not find manifests\guardrails.yaml or guardrails.yaml."
    }
}

Write-Ok "Using manifest: $guardrailsPath"

Write-Step "Applying Task 1 prerequisites"

$guardrails = Get-Content $guardrailsPath -Raw
$guardrails = $guardrails.Replace('${NS}', $Namespace)
$guardrails | kubectl -n $Namespace apply -f - | Out-Host

Write-Step "Verifying Task 1 resources"

$checks = @(
    @{ Kind = "resourcequota"; Name = "team-budget" },
    @{ Kind = "networkpolicy"; Name = "private-object-store" },
    @{ Kind = "serviceaccount"; Name = "observer" },
    @{ Kind = "role"; Name = "observer" },
    @{ Kind = "rolebinding"; Name = "observer" }
)

foreach ($check in $checks) {
    try {
        kubectl -n $Namespace get $check.Kind $check.Name -o name | Out-Null
        Write-Ok "$($check.Kind)/$($check.Name)"
    } catch {
        Fail "Missing required resource: $($check.Kind)/$($check.Name)"
    }
}

Write-Step "Showing current quota"

kubectl -n $Namespace get resourcequota team-budget | Out-Host

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Environment is ready to begin Task 2." -ForegroundColor Green
Write-Host "Context   : docker-desktop"
Write-Host "Namespace : $Namespace"
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Important:"
Write-Host "- This script recreates Task 1 prerequisites only."
Write-Host "- It does NOT rerun or overwrite Task 1 assessment evidence."
Write-Host "- Task 2 credentials must be generated locally and must not be committed."
Write-Host "- NetworkPolicy existence is verified here; enforcement is tested later in Task 3."
