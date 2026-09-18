# This installs/uninstalls the real EXE only on a disposable GitHub Windows runner.
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows' -or !$env:RUNNER_TEMP) {
    throw 'Installer integration tests require a disposable GitHub Windows runner.'
}
$repo = Split-Path -Parent $PSScriptRoot
$packages = @(Get-ChildItem -LiteralPath (Join-Path $repo 'artifacts/electron/dist') -Filter '*-Windows-x64-Setup.exe')
if ($packages.Count -ne 1) { throw 'Expected exactly one Windows installer.' }
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'
function Get-SoundShredderEntry {
    if (!(Test-Path -LiteralPath $uninstallKey)) { return @() }
    @(Get-ItemProperty "$uninstallKey\*" | Where-Object { $_.DisplayName -like 'SoundShredder*' })
}
if ((Get-SoundShredderEntry).Count) { throw 'Refusing to replace an existing registered installation.' }
$testRoot = [IO.Path]::GetFullPath((Join-Path $env:RUNNER_TEMP 'SoundShredder installer QA'))
$tempRoot = [IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\') + '\'
if (!$testRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $testRoot)) {
    throw 'Expected a new test directory inside RUNNER_TEMP.'
}
$installPath = Join-Path $testRoot 'App with spaces'
$profilePath = Join-Path $env:LOCALAPPDATA 'SoundShredder'
if ((Test-Path -LiteralPath $profilePath) -and !(Test-Path -LiteralPath $profilePath -PathType Container)) {
    throw 'The profile path is not a directory.'
}
$startMenu = [Environment]::GetFolderPath('Programs')
$uninstallLink = Join-Path $startMenu 'Uninstall SoundShredder.lnk'
if (Test-Path -LiteralPath $uninstallLink) { throw 'Unexpected existing uninstall shortcut.' }
$sentinel = [guid]::NewGuid().ToString()
$null = New-Item -ItemType Directory -Path $testRoot
$markers = @('data', 'runtimes', 'electron') | ForEach-Object {
    # Other regression checks can already have created this profile. Add only
    # unique test files and never clear or overwrite its existing content.
    $folder = Join-Path $profilePath "$_\installer-qa-$sentinel"
    $null = New-Item -ItemType Directory -Path $folder -Force
    $marker = Join-Path $folder 'retained.txt'
    Set-Content -LiteralPath $marker -Value $sentinel -NoNewline
    $marker
}

function Assert-ProfilePreserved {
    foreach ($marker in $markers) {
        if ((Get-Content -LiteralPath $marker -Raw) -ne $sentinel) { throw 'Installer changed saved profile data.' }
    }
}
function Run-Installer {
    # NSIS /D must be last and takes the entire remaining path, including spaces.
    $process = Start-Process -FilePath $packages[0].FullName -ArgumentList "/S /D=$installPath" -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) { throw "Installer failed: $($process.ExitCode)" }
    if (!(Test-Path -LiteralPath (Join-Path $installPath 'SoundShredder.exe'))) { throw 'App executable is missing.' }
    $entries = Get-SoundShredderEntry
    if ($entries.Count -ne 1) { throw 'Windows uninstall registration is missing or duplicated.' }
    $uninstaller = Join-Path $installPath 'Uninstall SoundShredder.exe'
    if (!(Test-Path -LiteralPath $uninstaller)) { throw 'Uninstaller is missing.' }
    $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($uninstallLink)
    if ($shortcut.TargetPath -ne $uninstaller -or $shortcut.Arguments -ne '/currentuser') {
        throw 'Start menu uninstall shortcut does not point at the installed uninstaller.'
    }
    if (!$entries[0].UninstallString.Contains($uninstaller)) { throw 'Windows Settings points at the wrong uninstaller.' }
    Assert-ProfilePreserved
}

Run-Installer
Write-Output 'Fresh installation, Windows Settings registration and uninstall shortcut passed.'
Run-Installer
Write-Output 'Reinstallation preserved profile data and restored uninstall access.'

# Run a copied uninstaller directly so Wait tracks the actual uninstall, not its
# temporary launcher. _?= supplies the exact, verified test installation folder.
$copy = Join-Path $testRoot 'uninstall-test.exe'
Copy-Item -LiteralPath (Join-Path $installPath 'Uninstall SoundShredder.exe') -Destination $copy
if (!(Resolve-Path -LiteralPath $installPath).Path.StartsWith($testRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing to uninstall outside the test installation.'
}
$process = Start-Process -FilePath $copy -ArgumentList "/S /currentuser _?=$installPath" -Wait -PassThru -WindowStyle Hidden
if ($process.ExitCode -ne 0) { throw "Uninstall failed: $($process.ExitCode)" }
if (Test-Path -LiteralPath (Join-Path $installPath 'SoundShredder.exe')) { throw 'Uninstall left the app executable.' }
if ((Get-SoundShredderEntry).Count -or (Test-Path -LiteralPath $uninstallLink)) { throw 'Uninstall left registration or its shortcut.' }
Assert-ProfilePreserved
Write-Output 'Uninstall removed application/registration/shortcut and preserved profile data.'

Run-Installer
Write-Output 'Installation after uninstall succeeded with saved profile data intact.'
# Subsequent processing and relaunch checks must exercise this installed copy.
Add-Content -LiteralPath $env:GITHUB_ENV -Value "SS_TEST_EXECUTABLE=$(Join-Path $installPath 'SoundShredder.exe')" -Encoding utf8
$report = Join-Path $repo 'artifacts/electron/verification/windows-installer.json'
$null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $report)
@{ fresh_install = $true; reinstall = $true; uninstall_shortcut = $true; windows_settings_registration = $true;
   uninstall = $true; profile_preserved = $true; install_after_uninstall = $true } |
    ConvertTo-Json | Set-Content -LiteralPath $report -Encoding utf8
# The runner is disposable. Leave its final installed copy available for inspection.
