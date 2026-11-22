param(
    [ValidateSet('display-v4','stock','full','liveview-dual','shutter-sound','m900')]
    [string]$Preset,
    [ValidateRange(1,65535)][int]$Port = 8787,
    [string]$BuildDirectory = '',
    [string]$WslDistro = 'Ubuntu',
    [switch]$MenuOnly,
    [switch]$Native,
    [switch]$OpenBrowser
)
$ErrorActionPreference = 'Stop'
if ($Native -and $PSBoundParameters.ContainsKey('WslDistro')) { throw 'Choose either -Native or -WslDistro.' }
$configuration = Join-Path $PSScriptRoot '.private/lab-environment.json'
$local = if (Test-Path -LiteralPath $configuration) { Get-Content -LiteralPath $configuration -Raw | ConvertFrom-Json } else { $null }
$explicitBuild = [bool]$BuildDirectory
if (-not $BuildDirectory) {
    $BuildDirectory = if ($local.build_directory) { $local.build_directory } else { '.private/builds/20261020-09' }
}
$buildPath = if ([IO.Path]::IsPathRooted($BuildDirectory)) { $BuildDirectory } else { Join-Path $PSScriptRoot $BuildDirectory }
if (-not $Preset) {
    if (Test-Path -LiteralPath (Join-Path $buildPath 'display.json') -PathType Leaf) { $Preset = 'display-v4' }
    elseif (-not $explicitBuild -and $local.preset) { $Preset = $local.preset }
    else { $Preset = 'full' }
}
$payloadName = switch ($Preset) {
    'display-v4' { 'display.emulator.main.bin' }
    'stock' { 'stock-main.bin' }
    default { "$Preset.main.bin" }
}
$payloadPath = Join-Path $buildPath $payloadName
if (-not (Test-Path -LiteralPath $payloadPath -PathType Leaf)) {
    throw "Firmware payload '$payloadPath' is missing. Run Setup-Z7.ps1 or select the matching -BuildDirectory and -Preset."
}
$currentFile = Join-Path $PSScriptRoot 'z7-qemu/.local/sessions/current.json'
if (Test-Path -LiteralPath $currentFile) {
    $current = Get-Content -LiteralPath $currentFile -Raw | ConvertFrom-Json
    $status = $null
    try { $status = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/status" -TimeoutSec 2 } catch { }
    if ($status -and $current.session -eq $status.session -and $current.url -eq "http://127.0.0.1:$Port") {
        $expectedFirmware = [IO.Path]::GetFullPath($payloadPath)
        $expectedPhoto = -not [bool]$MenuOnly
        if ($current.firmware_path -and [IO.Path]::GetFullPath($current.firmware_path) -eq $expectedFirmware -and [bool]$current.photo_liveview -eq $expectedPhoto) {
            if ($OpenBrowser) { Start-Process "$($current.url)/" }
            Write-Host "The selected app is already available at $($current.url)/"
            return
        }
        throw "A different lab session is using port $Port. Select another -Port."
    }
}
$launchArgs = @((Join-Path $PSScriptRoot 'tools/launch_z7.py'),'--preset',$Preset,'--port',"$Port",'--build-directory',$buildPath)
if ($MenuOnly) { $launchArgs += '--menu-only' }
if ($Native) { $launchArgs += '--native' }
elseif ($PSBoundParameters.ContainsKey('WslDistro')) { $launchArgs += @('--wsl','--wsl-distro',$WslDistro) }
$nativeRuntime = $Native -or (-not $PSBoundParameters.ContainsKey('WslDistro') -and $local.runtime -eq 'windows-native')
if ($Preset -eq 'display-v4' -and $nativeRuntime -and
    -not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'z7-qemu/.local/build-manifest.json') -PathType Leaf)) {
    throw 'Native QEMU is missing. Run Setup-Z7.ps1 -BuildQemu to prepare the emulator.'
}
$venv = if ($Preset -eq 'display-v4') { '.private/venv-v4' } else { '.venv' }
$localPython = Join-Path $PSScriptRoot "$venv/Scripts/python.exe"
$useConfiguredPython = ($Preset -eq 'display-v4') -eq ($local.preset -eq 'display-v4')
if ($useConfiguredPython -and $local.windows_python -and
    (Test-Path -LiteralPath $local.windows_python -PathType Leaf)) { $pythonCommand = $local.windows_python }
elseif (Test-Path -LiteralPath $localPython -PathType Leaf) { $pythonCommand = $localPython }
elseif (Get-Command py -ErrorAction SilentlyContinue) { $pythonCommand = (Get-Command py).Source; $launchArgs = @('-3') + $launchArgs }
else { $pythonCommand = (Get-Command python -ErrorAction Stop).Source }
$quotedArgs = $launchArgs | ForEach-Object { '"' + $_.Replace('"','\"') + '"' }
$logDirectory = Join-Path $PSScriptRoot '.private'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$logStamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$errorLog = Join-Path $logDirectory "launcher-$logStamp.stderr.log"
$process = Start-Process -FilePath $pythonCommand -ArgumentList $quotedArgs -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory "launcher-$logStamp.stdout.log") -RedirectStandardError $errorLog
if ($OpenBrowser) {
    $deadline = (Get-Date).AddSeconds(60)
    while (-not $process.HasExited -and (Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/api/status" -TimeoutSec 2
            if ($response.StatusCode -eq 200) { Start-Process "http://127.0.0.1:$Port/"; break }
        } catch { Start-Sleep -Milliseconds 250 }
        $process.Refresh()
    }
}
$process.WaitForExit()
$process.Refresh()
if ($process.ExitCode -ne 0) { Get-Content -LiteralPath $errorLog -Tail 30 | Write-Host }
if ($process.ExitCode -ne 0) { throw "Emulator exited with code $($process.ExitCode)" }
