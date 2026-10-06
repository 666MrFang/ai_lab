param(
    [Parameter(Mandatory=$true)][string]$Date,
    [ValidateSet("deepseek-flash","deepseek-v4-pro")][string]$Model = "deepseek-flash",
    [ValidateSet("auto","live","replay")][string]$Mode = "auto",
    [switch]$OverwriteOutput,
    [switch]$OpenDashboard
)

$ErrorActionPreference = "Stop"
if (-not $env:DEEPSEEK_API_KEY) {
    Write-Error "DEEPSEEK_API_KEY is not set in this PowerShell session."
    exit 2
}

$ReviewProduct = Join-Path $PSScriptRoot "..\review_product.py"
$Args = @(
    $ReviewProduct,
    "--date", $Date,
    "--mode", $Mode,
    "--agent", "deepseek",
    "--model", $Model
)
if ($OverwriteOutput) {
    $Args += "--overwrite-output"
}

& python @Args
$ExitCode = $LASTEXITCODE
if ($ExitCode -ne 0) {
    Write-Host "DAILY_REVIEW_STATUS=FAIL"
    exit $ExitCode
}

$Dashboard = Join-Path $PSScriptRoot "..\output\$Date\dashboard.html"
$Dashboard = [System.IO.Path]::GetFullPath($Dashboard)
Write-Host "DAILY_REVIEW_STATUS=SUCCESS"
Write-Host "DASHBOARD=$Dashboard"

if ($OpenDashboard) {
    if (Test-Path $Dashboard) {
        Start-Process $Dashboard
    } else {
        Write-Error "Dashboard was not created: $Dashboard"
        exit 3
    }
}
exit 0
