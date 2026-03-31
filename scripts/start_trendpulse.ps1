param(
    [string]$ApiBaseUrl = "",
    [string]$BackendHealthUrl = "http://127.0.0.1:8000/health",
    [string]$FlutterDevice = "",
    [string]$CondaEnvName = "android",
    [int]$HealthTimeoutSeconds = 90,
    [switch]$BackendOnly
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonEnvPath = Join-Path $projectRoot "python\.env"
$pythonEnvExamplePath = Join-Path $projectRoot "python\.env.example"

function Get-EnvFileValue {
    param(
        [string]$Path,
        [string]$Name
    )

    if (-not (Test-Path $Path)) {
        return $null
    }

    foreach ($line in Get-Content -Path $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }
        if ($trimmed -notmatch "=") {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim("'").Trim('"')
        if ($key -eq $Name) {
            return $value
        }
    }

    return $null
}

function Resolve-StartupEnvValue {
    param(
        [string]$Name
    )

    $fromProcess = [Environment]::GetEnvironmentVariable($Name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($fromProcess)) {
        return $fromProcess
    }

    $fromUser = [Environment]::GetEnvironmentVariable($Name, "User")
    if (-not [string]::IsNullOrWhiteSpace($fromUser)) {
        return $fromUser
    }

    $fromMachine = [Environment]::GetEnvironmentVariable($Name, "Machine")
    if (-not [string]::IsNullOrWhiteSpace($fromMachine)) {
        return $fromMachine
    }

    $fromDotEnv = Get-EnvFileValue -Path $pythonEnvPath -Name $Name
    if (-not [string]::IsNullOrWhiteSpace($fromDotEnv)) {
        return $fromDotEnv
    }

    return Get-EnvFileValue -Path $pythonEnvExamplePath -Name $Name
}

function Escape-PowerShellSingleQuotedString {
    param(
        [string]$Value
    )

    if ($null -eq $Value) {
        return ""
    }
    return $Value.Replace("'", "''")
}

function Normalize-StartupEnvValue {
    param(
        [string]$Name,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $Value
    }

    if ($Name -eq "DATABASE_URL" -and $Value -notmatch "://") {
        $normalizedPath = $Value.Replace("\", "/")
        return "sqlite:///$normalizedPath"
    }

    return $Value
}

function Build-StartupEnvAssignments {
    $envNames = @(
        "API_KEY",
        "BASE_URL",
        "LLM_API_BASE_URL",
        "LLM_MODEL",
        "LLM_TIMEOUT_SECONDS",
        "DATABASE_URL",
        "YOUTUBE_DATA_API_KEY",
        "YOUTUBE_PROXY_URL"
    )

    $assignments = @()
    foreach ($name in $envNames) {
        $value = Resolve-StartupEnvValue -Name $name
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            $value = Normalize-StartupEnvValue -Name $name -Value $value
            $escaped = Escape-PowerShellSingleQuotedString -Value $value
            $assignments += "`$env:$name='$escaped'"
        }
    }

    return ($assignments -join "; ")
}

function Build-StartupEnvSummary {
    $envNames = @(
        "API_KEY",
        "BASE_URL",
        "LLM_API_BASE_URL",
        "LLM_MODEL",
        "LLM_TIMEOUT_SECONDS",
        "DATABASE_URL",
        "YOUTUBE_DATA_API_KEY",
        "YOUTUBE_PROXY_URL"
    )

    $resolved = @()
    foreach ($name in $envNames) {
        $value = Resolve-StartupEnvValue -Name $name
        $status = if ([string]::IsNullOrWhiteSpace($value)) { "missing" } else { "loaded" }
        $resolved += "${name}=${status}"
    }

    return ($resolved -join ", ")
}

function Join-CommandParts {
    param(
        [string[]]$Parts
    )

    $nonEmptyParts = @()
    foreach ($part in $Parts) {
        if (-not [string]::IsNullOrWhiteSpace($part)) {
            $nonEmptyParts += $part
        }
    }

    return ($nonEmptyParts -join "; ")
}

function Start-BackendWindow {
    param(
        [string]$Root,
        [string]$EnvName,
        [string]$StartupEnvAssignments
    )

    $command = Join-CommandParts @(
        "Set-Location '$Root'",
        $StartupEnvAssignments,
        "conda activate $EnvName",
        "python python/examples/run_api.py"
    )
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        $command
    ) | Out-Null
}

function Wait-BackendHealthy {
    param(
        [string]$HealthUrl,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing $HealthUrl -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                return
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }

    throw "Backend did not become healthy within $TimeoutSeconds seconds. Check the backend window for errors."
}

function Start-FlutterWindow {
    param(
        [string]$Root,
        [string]$BaseUrl,
        [string]$Device,
        [string]$EnvName,
        [string]$StartupEnvAssignments
    )

    if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
        $flutterCommand = if ([string]::IsNullOrWhiteSpace($Device)) {
            "flutter run"
        } else {
            "flutter run -d $Device"
        }
    } else {
        $flutterCommand = if ([string]::IsNullOrWhiteSpace($Device)) {
            "flutter run --dart-define=API_BASE_URL=$BaseUrl"
        } else {
            "flutter run -d $Device --dart-define=API_BASE_URL=$BaseUrl"
        }
    }

    $command = Join-CommandParts @(
        "Set-Location '$Root'",
        $StartupEnvAssignments,
        "conda activate $EnvName",
        $flutterCommand
    )
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-Command",
        $command
    ) | Out-Null
}

Write-Host "Project root: $projectRoot"
Write-Host "Conda env: $CondaEnvName"
Write-Host "Preparing startup environment variables..."
$startupEnvAssignments = Build-StartupEnvAssignments
Write-Host ("Startup env status: " + (Build-StartupEnvSummary))
Write-Host "Starting backend..."
Start-BackendWindow -Root $projectRoot -EnvName $CondaEnvName -StartupEnvAssignments $startupEnvAssignments

Write-Host "Waiting for backend health check: $BackendHealthUrl"
Wait-BackendHealthy -HealthUrl $BackendHealthUrl -TimeoutSeconds $HealthTimeoutSeconds
Write-Host "Backend is healthy."

if (-not $BackendOnly) {
    if ([string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
        Write-Host "Starting Flutter with platform-aware API base URL."
    } else {
        Write-Host "Starting Flutter with API_BASE_URL=$ApiBaseUrl"
    }
    Start-FlutterWindow -Root $projectRoot -BaseUrl $ApiBaseUrl -Device $FlutterDevice -EnvName $CondaEnvName -StartupEnvAssignments $startupEnvAssignments
}

Write-Host "TrendPulse startup script completed."
