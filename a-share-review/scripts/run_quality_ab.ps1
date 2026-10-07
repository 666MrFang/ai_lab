param(
    [Parameter(Mandatory=$false)]
    [string]$Date = "2026-09-29",
    [ValidateSet("deepseek-flash", "deepseek-v4-pro")]
    [string]$Model = "deepseek-flash"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
if (-not $env:DEEPSEEK_API_KEY) {
    throw "DEEPSEEK_API_KEY is not configured in this PowerShell session."
}
Write-Host "QUALITY_AB|date=$Date|model=$Model|mode=replay"
python .\run_deepseek_ab.py --date $Date --model $Model
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$resultPath = Join-Path $Root ("experiments\runs\{0}-{1}\ab_result.json" -f $Date, $Model)
if (-not (Test-Path $resultPath)) { throw "A/B result not found: $resultPath" }
$result = Get-Content $resultPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($null -ne $result.quality) {
    $referenceScore = $result.quality.reference
    $candidateScore = $result.quality.candidate
    Write-Host ("QUALITY_AB_RESULT|reference={0}/{1}|candidate={2}/{3}|delta={4}" -f $referenceScore.score, $referenceScore.max_score, $candidateScore.score, $candidateScore.max_score, $result.quality.candidate_minus_reference)
}
Write-Host "QUALITY_AB_FILE|$resultPath"
