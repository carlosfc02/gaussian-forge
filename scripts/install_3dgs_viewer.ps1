$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$viewerDir = Join-Path $repoRoot 'tools\3dgs-viewer'
$zipPath = Join-Path $viewerDir 'viewers.zip'
$installDir = Join-Path $viewerDir 'viewer-dist'
$url = 'https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/binaries/viewers.zip'

New-Item -ItemType Directory -Force $viewerDir | Out-Null

if (-not (Test-Path $zipPath)) {
    Write-Host "Downloading official 3DGS viewers..."
    Invoke-WebRequest -Uri $url -OutFile $zipPath
}
else {
    Write-Host "Viewer archive already present: $zipPath"
}

Write-Host "Extracting viewer archive..."
Expand-Archive -Force $zipPath $installDir

$viewerExe = Join-Path $installDir 'bin\SIBR_gaussianViewer_app.exe'
if (-not (Test-Path $viewerExe)) {
    throw "Viewer executable not found after extraction: $viewerExe"
}

Write-Host "Viewer ready at: $viewerExe"
