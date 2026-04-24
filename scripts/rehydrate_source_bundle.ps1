$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..")
$bootstrapDir = Join-Path $repoRoot ".github\bootstrap"
$zipPath = Join-Path $repoRoot "calds-runtime-github-publish.zip"

$parts = Get-ChildItem -Path $bootstrapDir -Filter "calds-runtime-github-publish.zip.b64.*" | Sort-Object Name
if ($parts.Count -eq 0) {
    throw "No bootstrap bundle parts found in $bootstrapDir"
}

$b64 = ($parts | ForEach-Object { Get-Content $_.FullName -Raw }) -join ""
[IO.File]::WriteAllBytes($zipPath, [Convert]::FromBase64String($b64))
Expand-Archive -Path $zipPath -DestinationPath $repoRoot -Force
Remove-Item $zipPath -Force
Write-Host "Rehydrated CalDS source bundle into $repoRoot"
