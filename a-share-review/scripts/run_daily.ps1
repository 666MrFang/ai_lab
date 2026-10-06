param(
    [Parameter(Mandatory=$true)][string]$Date,
    [ValidateSet("deepseek-flash","deepseek-v4-pro")][string]$Model = "deepseek-flash",
    [ValidateSet("auto","live","replay")][string]$Mode = "auto"
)

$ErrorActionPreference = "Stop"
if (-not $env:DEEPSEEK_API_KEY) {
    Write-Error "DEEPSEEK_API_KEY is not set in this PowerShell session."
    exit 2
}

python "$PSScriptRoot\..\review_product.py" --date $Date --mode $Mode --agent deepseek --model $Model
exit $LASTEXITCODE
