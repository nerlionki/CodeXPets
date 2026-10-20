$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$exe = Join-Path $projectRoot 'dist/CodeXPets-1.0.0-Windows-Setup.exe'
$testRoot = Join-Path $projectRoot ('build/installer-test-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
$checks = [System.Collections.Generic.List[string]]::new()
function Invoke-Installer([string[]]$Arguments, [int]$ExpectedExit = 0) {
    $quoted = ($Arguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
    $process = Start-Process -FilePath $exe -ArgumentList $quoted -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne $ExpectedExit) { throw "Unexpected exit $($process.ExitCode): $quoted" }
}
function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
    $checks.Add($Message)
}
$verify = Join-Path $testRoot 'verify.json'
Invoke-Installer @('--verify-assets', $verify)
$assetReport = Get-Content -LiteralPath $verify -Raw | ConvertFrom-Json
Assert-True $assetReport.ok 'Embedded resources and SHA256 checks pass'
$homeDir = Join-Path $testRoot '中文 用户/.codex'
$unrelated = Join-Path $homeDir 'pets/other-pet'
New-Item -ItemType Directory -Path $unrelated -Force | Out-Null
[IO.File]::WriteAllText((Join-Path $unrelated 'keep.txt'), 'keep another pet')
[IO.File]::WriteAllText((Join-Path $homeDir 'config.toml'), '# preserve Codex settings')
$firstReport = Join-Path $testRoot 'first.json'
Invoke-Installer @('--install-to', $homeDir, '--report', $firstReport)
$first = Get-Content -LiteralPath $firstReport -Raw | ConvertFrom-Json
$target = Join-Path $homeDir 'pets/maltese-retriever'
Assert-True ($first.ok -and $null -eq $first.backup) 'First install into a path with Chinese characters and spaces succeeds'
Assert-True ((Get-FileHash -LiteralPath (Join-Path $target 'spritesheet.webp')).Hash.ToLowerInvariant() -eq $assetReport.spriteSha256) 'Installed sprite matches embedded resource'
Assert-True ((Get-FileHash -LiteralPath (Join-Path $target 'pet.json')).Hash.ToLowerInvariant() -eq $assetReport.manifestSha256) 'Installed pet manifest matches embedded resource'
[IO.File]::WriteAllText((Join-Path $target 'extra.txt'), 'previous custom files')
$secondReport = Join-Path $testRoot 'second.json'
Invoke-Installer @('--install-to', $homeDir, '--report', $secondReport)
$second = Get-Content -LiteralPath $secondReport -Raw | ConvertFrom-Json
Assert-True ($second.ok -and (Test-Path -LiteralPath (Join-Path $second.backup 'extra.txt'))) 'Repeat install preserves complete previous pet in backup'
Assert-True ((Split-Path $second.backup -Parent) -eq (Join-Path $homeDir 'pet-backups')) 'Backup stays outside the selectable pets folder'
Assert-True ((Get-ChildItem -LiteralPath (Join-Path $homeDir 'pets') -Directory).Count -eq 2) 'Repeat install creates no duplicate pet entries'
Assert-True (([IO.File]::ReadAllText((Join-Path $unrelated 'keep.txt'))) -eq 'keep another pet') 'Other pets remain unchanged'
Assert-True (([IO.File]::ReadAllText((Join-Path $homeDir 'config.toml'))) -eq '# preserve Codex settings') 'Codex settings remain unchanged'
$blockedHome = Join-Path $testRoot 'blocked/.codex'
New-Item -ItemType Directory -Path (Join-Path $blockedHome 'pets') -Force | Out-Null
$blockingFile = Join-Path $blockedHome 'pets/maltese-retriever'
[IO.File]::WriteAllText($blockingFile, 'do not replace')
$failedReport = Join-Path $testRoot 'blocked.json'
Invoke-Installer @('--install-to', $blockedHome, '--report', $failedReport) 1
Assert-True (([IO.File]::ReadAllText($blockingFile)) -eq 'do not replace') 'Failed install preserves a conflicting existing file'
Assert-True ((Get-ChildItem -LiteralPath $homeDir -Filter '.pet-installer-*' -Force).Count -eq 0) 'Successful installs leave no staging residue'
Assert-True ((Get-ChildItem -LiteralPath $blockedHome -Filter '.pet-installer-*' -Force).Count -eq 0) 'Failed install leaves no staging residue'
Invoke-Installer @('--render-preview', (Join-Path $testRoot 'window.png'))
Invoke-Installer @('--render-preview', (Join-Path $testRoot 'window-large.png'), 'large')
$result = [ordered]@{ ok = $true; checks = $checks; testRoot = $testRoot; testedOS = [Environment]::OSVersion.VersionString; testedArchitecture = if ([Environment]::Is64BitOperatingSystem) { 'x64' } else { 'x86' }; target = 'Windows 10 and Windows 11; additional OS versions not machine-tested'; installedInRealCodex = $false }
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $projectRoot 'release/1.0.0/installer-tests.json') -Encoding UTF8
$result | ConvertTo-Json -Depth 6
