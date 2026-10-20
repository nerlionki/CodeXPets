param([string]$OutputName = 'CodeXPets-1.0.0-Windows-Setup.exe')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$buildDir = Join-Path $projectRoot 'build/installer'
$distDir = Join-Path $projectRoot 'dist'
New-Item -ItemType Directory -Force -Path $buildDir, $distDir | Out-Null
$sprite = Join-Path $distDir 'maltese-retriever/spritesheet.webp'
$manifest = Join-Path $distDir 'maltese-retriever/pet.json'
$preview = Join-Path $projectRoot 'animation/pet-run/qa/previews/idle.gif'
foreach ($asset in @($sprite, $manifest, $preview)) {
    if (-not (Test-Path -LiteralPath $asset -PathType Leaf)) { throw "Missing asset: $asset" }
}
$spriteHash = (Get-FileHash -LiteralPath $sprite -Algorithm SHA256).Hash.ToLowerInvariant()
$manifestHash = (Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant()
$previewHash = (Get-FileHash -LiteralPath $preview -Algorithm SHA256).Hash.ToLowerInvariant()
$buildInfo = Join-Path $buildDir 'BuildInfo.cs'
@"
namespace CodeXPets {
    internal static class BuildInfo {
        internal const string SpriteSha256 = "$spriteHash";
        internal const string ManifestSha256 = "$manifestHash";
        internal const string PreviewSha256 = "$previewHash";
    }
}
"@ | Set-Content -LiteralPath $buildInfo -Encoding UTF8
$compiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework/v4.0.30319/csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw '.NET Framework C# compiler not found.' }
$output = Join-Path $distDir $OutputName
$compilerArgs = @(
    '/nologo', '/target:winexe', '/platform:anycpu', '/optimize+', '/codepage:65001', '/utf8output',
    "/out:$output", "/win32manifest:$(Join-Path $PSScriptRoot 'app.manifest')",
    '/reference:System.dll', '/reference:System.Core.dll', '/reference:System.Drawing.dll',
    '/reference:System.Windows.Forms.dll', '/reference:System.Web.Extensions.dll',
    "/resource:$sprite,CodeXPets.Sprite", "/resource:$manifest,CodeXPets.Manifest", "/resource:$preview,CodeXPets.Preview",
    (Join-Path $PSScriptRoot 'Program.cs'), $buildInfo
)
& $compiler @compilerArgs
if ($LASTEXITCODE -ne 0) { throw "Compiler failed: $LASTEXITCODE" }
$exeHash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant()
$hashLines = @("$exeHash  $OutputName")
foreach ($assetName in @('maltese-retriever-1.0.0.zip', 'INSTALL.txt')) {
    $assetPath = Join-Path $distDir $assetName
    if (Test-Path -LiteralPath $assetPath -PathType Leaf) {
        $assetHash = (Get-FileHash -LiteralPath $assetPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $hashLines += "$assetHash  $assetName"
    }
}
$hashLines | Set-Content -LiteralPath (Join-Path $distDir 'SHA256SUMS.txt') -Encoding ASCII
Write-Output $output
Write-Output "SHA256: $exeHash"
