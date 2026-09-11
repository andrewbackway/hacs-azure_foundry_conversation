#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [ValidateSet("patch", "minor", "major")]
    [string]$Bump = "patch",
    [string]$Version,
    [string]$Remote = "origin",
    [switch]$NoPush,
    [switch]$NoRelease
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ManifestPath = Join-Path $RepoRoot "custom_components/azure_foundry_conversation/manifest.json"
if (-not (Test-Path $ManifestPath)) {
    throw "Required file not found: $ManifestPath"
}

$manifestText = Get-Content $ManifestPath -Raw
$versionMatch = [regex]::Match($manifestText, '"version"\s*:\s*"(?<version>\d+\.\d+\.\d+)"')
if (-not $versionMatch.Success) {
    throw "Could not find a semantic version in: $ManifestPath"
}

$current = $versionMatch.Groups["version"].Value
if ($Version) {
    if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Version must be X.Y.Z" }
    $new = $Version
} else {
    $parts = $current.Split(".")
    [int]$major = $parts[0]
    [int]$minor = $parts[1]
    [int]$patch = $parts[2]
    switch ($Bump) {
        "major" { $major++; $minor = 0; $patch = 0 }
        "minor" { $minor++; $patch = 0 }
        "patch" { $patch++ }
    }
    $new = "$major.$minor.$patch"
}
if ($new -eq $current) { throw "New version matches current version" }

$dirty = git -C $RepoRoot status --porcelain
if ($dirty) { throw "Working tree is not clean:`n$dirty" }

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m pytest
} else {
    & python -m pytest
}
if ($LASTEXITCODE -ne 0) { throw "Tests failed with exit code $LASTEXITCODE" }

$replacement = '"version": "' + $new + '"'
$updatedManifest = $versionMatch.Result($replacement)
[System.IO.File]::WriteAllText(
    $ManifestPath,
    $manifestText.Substring(0, $versionMatch.Index) +
    $updatedManifest +
    $manifestText.Substring($versionMatch.Index + $versionMatch.Length)
)

$tag = "v$new"
git -C $RepoRoot add custom_components/azure_foundry_conversation/manifest.json
git -C $RepoRoot commit -m "Release $tag"
git -C $RepoRoot tag $tag
if ($NoPush) { Write-Host "Created $tag locally."; return }
$branch = git -C $RepoRoot rev-parse --abbrev-ref HEAD
git -C $RepoRoot push $Remote $branch
git -C $RepoRoot push $Remote $tag
if ($NoRelease) { return }
$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) { Write-Warning "gh not found; tag pushed without a GitHub release."; return }
gh release create $tag --repo andrewbackway/hacs-azure_foundry_conversation --title $tag --generate-notes
