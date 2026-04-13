param(
    [string]$SceneDir,
    [string]$ModelDir,
    [string]$SourceDir,
    [int]$Iteration,
    [switch]$LoadImages,
    [switch]$NoInterop,
    [switch]$PrintOnly
)

$ErrorActionPreference = 'Stop'

function Test-Cuda12Runtime {
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($env:PATH) {
        foreach ($entry in ($env:PATH -split ';')) {
            if ($entry) {
                $candidates.Add($entry)
            }
        }
    }

    if ($env:LOCALAPPDATA) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA 'NVIDIA\cuda-cudart-12.4.127\cuda_cudart-windows-x86_64-12.4.127-archive\bin'))
    }

    $candidates.Add('C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin')
    $candidates.Add('C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1\bin')
    $candidates.Add('C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2\bin')
    $candidates.Add('C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.3\bin')
    $candidates.Add('C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin')
    $candidates.Add('C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5\bin')
    $candidates.Add('C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin')
    $candidates.Add('C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8\bin')

    foreach ($dir in ($candidates | Select-Object -Unique)) {
        try {
            $dllPath = Join-Path $dir 'cudart64_12.dll'
            if (Test-Path $dllPath) {
                return $dllPath
            }
        }
        catch {
        }
    }
    return $null
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$viewerRoot = Join-Path $repoRoot 'tools\3dgs-viewer\viewer-dist'
$viewerExe = Join-Path $viewerRoot 'bin\SIBR_gaussianViewer_app.exe'

if (-not (Test-Path $viewerExe)) {
    throw "3DGS viewer not found at $viewerExe. Run scripts\install_3dgs_viewer.ps1 first."
}

$cudaRuntime = Test-Cuda12Runtime
if (-not $cudaRuntime) {
    throw @"
CUDA 12 runtime not found on Windows.
The official SIBR 3DGS viewer requires cudart64_12.dll.
Install a CUDA 12.x toolkit/runtime on Windows, or place cudart64_12.dll in the viewer bin directory or in your PATH.
Your current PATH appears to include CUDA 13, which is not enough for this viewer build.
"@
}

$cudaRuntimeDir = Split-Path -Parent $cudaRuntime
if ($env:PATH -notlike "*$cudaRuntimeDir*") {
    $env:PATH = "$cudaRuntimeDir;$env:PATH"
}

if (-not $SceneDir -and -not $ModelDir) {
    throw 'Provide -SceneDir <scene> or -ModelDir <path>.'
}

if ($SceneDir) {
    $sceneRoot = Join-Path $repoRoot (Join-Path 'data' $SceneDir)
    if (-not $ModelDir) {
        $ModelDir = Join-Path $sceneRoot 'gs\model'
    }
    if (-not $SourceDir) {
        $SourceDir = Join-Path $sceneRoot 'gs\source'
    }
}
else {
    if (-not $SourceDir) {
        $modelParent = Split-Path -Parent $ModelDir
        $SourceDir = Join-Path $modelParent 'source'
    }
}

$resolvedModelDir = Convert-Path $ModelDir
$resolvedSourceDir = Convert-Path $SourceDir
$resolvedViewerRoot = Convert-Path $viewerRoot

if (-not (Test-Path $resolvedModelDir)) {
    throw "Model directory does not exist: $resolvedModelDir"
}
if (-not (Test-Path $resolvedSourceDir)) {
    throw "Source directory does not exist: $resolvedSourceDir"
}

$argsList = @(
    '-m', $resolvedModelDir,
    '-s', $resolvedSourceDir
)

if ($PSBoundParameters.ContainsKey('Iteration')) {
    $argsList += @('--iteration', $Iteration)
}
if ($LoadImages) {
    $argsList += '--load_images'
}
if ($NoInterop) {
    $argsList += '--no_interop'
}

Write-Host "Launching 3DGS viewer..."
Write-Host "  viewer: $viewerExe"
Write-Host "  model : $resolvedModelDir"
Write-Host "  source: $resolvedSourceDir"
Write-Host "  cudart: $cudaRuntime"
Write-Host "  args  : $($argsList -join ' ')"

if ($PrintOnly) {
    return
}

Start-Process -FilePath $viewerExe -WorkingDirectory $resolvedViewerRoot -ArgumentList $argsList
