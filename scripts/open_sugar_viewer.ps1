param(
    [string]$PlyPath,
    [string]$SourceDir,
    [string]$BaseModelDir,
    [string]$ViewerModelDir,
    [switch]$LoadImages,
    [switch]$NoInterop,
    [switch]$PrintOnly
)

$ErrorActionPreference = 'Stop'

function Resolve-DataRelativePath {
    param(
        [string]$RepoRoot,
        [string]$InputPath
    )

    if (-not $InputPath) {
        return $null
    }

    if ([System.IO.Path]::IsPathRooted($InputPath)) {
        return (Convert-Path $InputPath)
    }

    $candidate = Join-Path $RepoRoot (Join-Path 'data' $InputPath)
    if (Test-Path $candidate) {
        return (Convert-Path $candidate)
    }

    $candidate = Join-Path $RepoRoot $InputPath
    if (Test-Path $candidate) {
        return (Convert-Path $candidate)
    }

    throw "Path does not exist: $InputPath"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

if (-not $PlyPath) {
    throw 'Provide -PlyPath <path to SuGaR refined_ply .ply>.'
}
if (-not $SourceDir) {
    throw 'Provide -SourceDir <path to the corresponding gs/source dataset>.'
}

$resolvedPlyPath = Resolve-DataRelativePath -RepoRoot $repoRoot -InputPath $PlyPath
$resolvedSourceDir = Resolve-DataRelativePath -RepoRoot $repoRoot -InputPath $SourceDir

if (-not $resolvedPlyPath.ToLowerInvariant().EndsWith('.ply')) {
    throw "Ply path must point to a .ply file: $resolvedPlyPath"
}
if (-not (Test-Path $resolvedSourceDir)) {
    throw "Source directory does not exist: $resolvedSourceDir"
}

if (-not $BaseModelDir) {
    $defaultBaseModelDir = Join-Path (Split-Path -Parent $resolvedSourceDir) 'model'
    if (-not (Test-Path $defaultBaseModelDir)) {
        throw @"
Base 3DGS model directory not found automatically.
Provide -BaseModelDir <path to the original gs/model directory>.
Tried: $defaultBaseModelDir
"@
    }
    $BaseModelDir = $defaultBaseModelDir
}

$resolvedBaseModelDir = Resolve-DataRelativePath -RepoRoot $repoRoot -InputPath $BaseModelDir

if (-not $ViewerModelDir) {
    $plyStem = [System.IO.Path]::GetFileNameWithoutExtension($resolvedPlyPath)
    $ViewerModelDir = Join-Path $repoRoot (Join-Path 'data' (Join-Path 'sugar_output\viewer' $plyStem))
}
elseif (-not [System.IO.Path]::IsPathRooted($ViewerModelDir)) {
    $ViewerModelDir = Join-Path $repoRoot (Join-Path 'data' $ViewerModelDir)
}

$viewerModelDirPath = [System.IO.Path]::GetFullPath($ViewerModelDir)
$pointCloudDir = Join-Path $viewerModelDirPath 'point_cloud\iteration_0'

New-Item -ItemType Directory -Force $pointCloudDir | Out-Null

Copy-Item $resolvedPlyPath (Join-Path $pointCloudDir 'point_cloud.ply') -Force

foreach ($filename in @('cfg_args', 'cameras.json', 'input.ply', 'exposure.json')) {
    $sourceFile = Join-Path $resolvedBaseModelDir $filename
    if (Test-Path $sourceFile) {
        Copy-Item $sourceFile (Join-Path $viewerModelDirPath $filename) -Force
    }
}

if (-not (Test-Path (Join-Path $viewerModelDirPath 'cfg_args'))) {
    throw "Could not prepare viewer model because cfg_args was not found in base model dir: $resolvedBaseModelDir"
}

$openViewerScript = Join-Path $scriptDir 'open_3dgs_viewer.ps1'
$invokeArgs = @(
    '-ExecutionPolicy', 'Bypass',
    '-File', $openViewerScript,
    '-ModelDir', $viewerModelDirPath,
    '-SourceDir', $resolvedSourceDir,
    '-Iteration', '0'
)

if ($LoadImages) {
    $invokeArgs += '-LoadImages'
}
if ($NoInterop) {
    $invokeArgs += '-NoInterop'
}
if ($PrintOnly) {
    $invokeArgs += '-PrintOnly'
}

Write-Host "Prepared SuGaR viewer model:"
Write-Host "  ply       : $resolvedPlyPath"
Write-Host "  source    : $resolvedSourceDir"
Write-Host "  base model: $resolvedBaseModelDir"
Write-Host "  viewer dir: $viewerModelDirPath"
Write-Host "  args      : $($invokeArgs -join ' ')"

& powershell @invokeArgs
