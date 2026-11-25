param(
    [string]$PythonPath = '',
    [string]$SourceFirmware = (Join-Path $env:USERPROFILE 'Downloads/Z_7_0380.bin'),
    [string]$BuildDirectory = '',
    [string]$LlvmBin = '',
    [ValidateRange(1,64)][int]$Jobs = 4,
    [switch]$BuildQemu,
    [switch]$Legacy,
    [switch]$SkipQemu
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$sourceExplicit = $PSBoundParameters.ContainsKey('SourceFirmware')
$SourceFirmware = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($SourceFirmware)
if ($PythonPath) { $PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path }
if ($LlvmBin) { $LlvmBin = (Resolve-Path -LiteralPath $LlvmBin).Path }
if ($BuildQemu -and $SkipQemu) { throw 'Choose either -BuildQemu or -SkipQemu.' }
$previousSystem = $env:MSYSTEM
$previousDirectory = $env:CHERE_INVOKING
Push-Location $PSScriptRoot
try {
    function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
        & $Executable @Arguments
        if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE" }
    }
    function Write-Utf8([string]$Path, [string]$Content) {
        [IO.File]::WriteAllText($Path, $Content, (New-Object Text.UTF8Encoding $false))
    }
    function Get-ToolchainArchive([string]$Uri, [string]$File, [string]$Sha256) {
        $ProgressPreference = 'SilentlyContinue'
        $archive = Join-Path $PSScriptRoot ".private/downloads/$File"
        if ((Test-Path -LiteralPath $archive -PathType Leaf) -and
            (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -eq $Sha256) {
            return $archive
        }
        Invoke-WebRequest -UseBasicParsing -Uri $Uri -OutFile "$archive.part" -TimeoutSec 600
        if ((Get-FileHash -LiteralPath "$archive.part" -Algorithm SHA256).Hash -ne $Sha256) {
            throw "$File SHA-256 mismatch."
        }
        Move-Item -LiteralPath "$archive.part" -Destination $archive -Force
        return $archive
    }
    function Test-Python312([string]$Executable, [string[]]$Arguments) {
        if (-not $Executable) { return $false }
        try {
            & $Executable @Arguments -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>$null
            return $LASTEXITCODE -eq 0
        } catch { return $false }
    }
    $toolchain = Join-Path $PSScriptRoot '.private/toolchain'
    New-Item -ItemType Directory -Path .private/stock,.private/downloads,$toolchain -Force | Out-Null
    $stock = Join-Path $PSScriptRoot '.private/stock/Z_7_0380.bin'
    $expected = '07cf19513ada5b770caec4cfc3531a6734c48aede28dcec037f0f8374ef441a2'
    $stockExists = Test-Path -LiteralPath $stock -PathType Leaf
    $inputFirmware = if ($sourceExplicit -or -not $stockExists) { $SourceFirmware } else { $stock }
    if (-not (Test-Path -LiteralPath $inputFirmware -PathType Leaf)) {
        throw "Original Z_7_0380.bin not found at '$inputFirmware'. Supply its local path with -SourceFirmware."
    }
    if ((Get-FileHash -LiteralPath $inputFirmware -Algorithm SHA256).Hash -ne $expected) {
        throw "Original Nikon Z7 C 3.80 container SHA-256 mismatch at '$inputFirmware'."
    }
    if (-not $stockExists) { [IO.File]::Copy($inputFirmware, $stock) }
    if ($inputFirmware -ne $stock -and (Get-FileHash -LiteralPath $stock -Algorithm SHA256).Hash -ne $expected) {
        throw "Cached stock firmware SHA-256 mismatch at '$stock'."
    }
    if (-not $BuildDirectory) {
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
        $BuildDirectory = if ($Legacy) { ".private/builds/$stamp" } else { ".private/builds/display-v1.5-$stamp" }
    }
    $BuildDirectory = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($BuildDirectory)
    if (Test-Path -LiteralPath $BuildDirectory) { throw 'Use a new BuildDirectory to preserve earlier candidates.' }
    $venv = Join-Path $PSScriptRoot $(if ($Legacy) { '.venv' } else { '.private/venv-v4' })
    $python = Join-Path $venv 'Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        $pythonArgs = @()
        if (-not $PythonPath) {
            foreach ($candidate in @(
                (Join-Path $PSScriptRoot '.private/python-runtime/python.exe'),
                (Join-Path $toolchain 'python/python.exe')
            )) {
                if ((Test-Path -LiteralPath $candidate -PathType Leaf) -and (Test-Python312 $candidate @())) {
                    $PythonPath = $candidate
                    break
                }
            }
        }
        if (-not $PythonPath) {
            $py = Get-Command py.exe -ErrorAction SilentlyContinue
            $systemPython = Get-Command python.exe -ErrorAction SilentlyContinue
            if ($py -and (Test-Python312 $py.Source @('-3.12'))) {
                $PythonPath = $py.Source
                $pythonArgs = @('-3.12')
            } elseif ($systemPython -and $systemPython.Source -notlike '*\Microsoft\WindowsApps\*' -and
                      (Test-Python312 $systemPython.Source @())) {
                $PythonPath = $systemPython.Source
            } else {
                $archive = Get-ToolchainArchive `
                    'https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.12.16%2B20261110-x86_64-pc-windows-msvc-install_only_stripped.tar.gz' `
                    'cpython-3.12.16-windows-x64.tar.gz' `
                    '355ee61b8207b91574491b1c6dc9b0ebb4408fc56bfafe498f3ef439314b52dc'
                Invoke-Checked 'tar.exe' @('-xf',$archive,'-C',$toolchain)
                $PythonPath = Join-Path $toolchain 'python/python.exe'
            }
        }
        if (-not (Test-Python312 $PythonPath $pythonArgs)) { throw 'Python 3.12 or newer is required.' }
        Invoke-Checked $PythonPath ($pythonArgs + @('-m','venv',$venv))
    }
    if (-not (Test-Python312 $python @())) { throw "Python 3.12 or newer is required in '$venv'." }
    $pipArgs = @('-m','pip','install','-e','./z7-firmware-extensions[type-a]')
    if ($Legacy -or $BuildQemu) { $pipArgs += @('-r','requirements-lab.txt') }
    Invoke-Checked $python $pipArgs

    if (-not $Legacy) {
        if (-not $LlvmBin) {
            $llvmName = 'llvm-mingw-20261104-ucrt-x86_64'
            $LlvmBin = Join-Path $toolchain "$llvmName/bin"
            if (-not (Test-Path -LiteralPath (Join-Path $LlvmBin 'ld.lld.exe') -PathType Leaf)) {
                $archive = Get-ToolchainArchive `
                    "https://github.com/mstorsjo/llvm-mingw/releases/download/20261104/$llvmName.zip" `
                    "$llvmName.zip" '552191b5754c49a5a20723276a6fc56541ea1922c4c50b7b669022333fc1b40f'
                Invoke-Checked 'tar.exe' @('-xf',$archive,'-C',$toolchain)
            }
        }
        foreach ($tool in @('clang.exe','ld.lld.exe')) {
            if (-not (Test-Path -LiteralPath (Join-Path $LlvmBin $tool) -PathType Leaf)) {
                throw "Missing $tool in '$LlvmBin'. Supply the LLVM bin directory with -LlvmBin."
            }
        }
        Invoke-Checked $python @('tools/build_display_type_a.py','--source',$stock,'--llvm-bin',$LlvmBin,'--output',$BuildDirectory,'--af-on-af-c')
        $reference = Get-Content -LiteralPath evidence/v1.5-reference.json -Raw | ConvertFrom-Json
        $egHash = (Get-FileHash -LiteralPath (Join-Path $BuildDirectory 'display.emulator.eg.bin') -Algorithm SHA256).Hash.ToLowerInvariant()
        $mainHash = (Get-FileHash -LiteralPath (Join-Path $BuildDirectory 'display.emulator.main.bin') -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($egHash -ne $reference.eg_sha256 -or $mainHash -ne $reference.main_sha256) {
            throw "V1.5 release hash mismatch. Expected EG $($reference.eg_sha256) and MAIN $($reference.main_sha256), got EG $egHash and MAIN $mainHash. Check the Clang/LLD version."
        }
        Write-Host "Verified V1.5 EG SHA-256 $egHash and MAIN SHA-256 $mainHash"
    }

    $msys = Join-Path $toolchain 'msys64'
    if ($BuildQemu -or ($Legacy -and -not $SkipQemu)) {
        if (-not (Test-Path -LiteralPath (Join-Path $msys 'usr/bin/bash.exe'))) {
            $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/msys2/msys2-installer/releases/latest'
            $asset = $release.assets | Where-Object name -Match '^msys2-base-x86_64-.*\.sfx\.exe$' | Select-Object -First 1
            if (-not $asset -or $asset.digest -notmatch '^sha256:[a-f0-9]{64}$') { throw 'MSYS2 release lacks a SHA-256 digest' }
            $archive = Join-Path $PSScriptRoot '.private/downloads/msys2-base.sfx.exe'
            Invoke-WebRequest -UseBasicParsing -Uri $asset.browser_download_url -OutFile $archive
            if ('sha256:' + (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $asset.digest) {
                throw 'MSYS2 release archive digest mismatch'
            }
            $asset | ConvertTo-Json -Depth 5 | Set-Content .private/downloads/msys2-release.json
            Invoke-Checked $archive @('-y',('-o' + (Join-Path $PSScriptRoot '.private/toolchain')))
        }
        $env:MSYSTEM = 'UCRT64'
        $env:CHERE_INVOKING = 'yes'
        $bash = Join-Path $msys 'usr/bin/bash.exe'
        Invoke-Checked $bash @('-lc','pacman -Syu --noconfirm')
        # Reopen after core updates, as required by MSYS2.
        Invoke-Checked $bash @('-lc','pacman -Syu --noconfirm')
        Invoke-Checked $bash @('-lc','pacman -S --needed --noconfirm make diffutils mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-glib2 mingw-w64-ucrt-x86_64-pixman mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-meson mingw-w64-ucrt-x86_64-dtc mingw-w64-ucrt-x86_64-zlib')
        $qemuArgs = @('z7-qemu/tools/build.py','--work-dir','.private/qemu','--msys-root',$msys,'--jobs',"$Jobs")
        if (Test-Path -LiteralPath .private/downloads/qemu-10.2.4.tar.xz) { $qemuArgs += @('--archive','.private/downloads/qemu-10.2.4.tar.xz') }
        Invoke-Checked $python $qemuArgs
    }
    if ($Legacy -or $BuildQemu) {
        & (Join-Path $PSScriptRoot 'tools/check_windows.ps1') -MsysRoot $msys -PythonPath $python
        Invoke-Checked $python @('z7-qemu/tools/make_cmos.py')
    }
    if ($Legacy) {
        Invoke-Checked $python @('tools/build_firmware.py','--output',$BuildDirectory)
        Invoke-Checked $python @('tools/check_candidate_inputs.py','--build',$BuildDirectory)
    }
    $configuration = @{
        runtime = 'windows-native'
        windows_python = $python
        msys_root = $msys
        build_directory = $BuildDirectory
        preset = $(if ($Legacy) { 'full' } else { 'display-v4' })
        llvm_bin = $LlvmBin
    } | ConvertTo-Json
    Write-Utf8 (Join-Path $PSScriptRoot '.private/lab-environment.json') ($configuration + "`n")
    Write-Host "Build saved to $BuildDirectory"
    if ($Legacy -or $BuildQemu) { Write-Host 'Start the local app with .\Run-Z7.ps1' }
} finally {
    $env:MSYSTEM = $previousSystem
    $env:CHERE_INVOKING = $previousDirectory
    Pop-Location
}
