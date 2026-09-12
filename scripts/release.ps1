#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [ValidateSet("patch", "minor", "major")]
    [string]$Bump = "patch",
    [string]$Version,
    [string]$Remote = "origin",
    [switch]$Push,
    [switch]$Release
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$ManifestPath = Join-Path $RepoRoot "custom_components/azure_foundry_conversation/manifest.json"
if (-not (Test-Path $ManifestPath)) { throw "Required file not found: $ManifestPath" }

$manifestRaw = Get-Content $ManifestPath -Raw
$manifest = $manifestRaw | ConvertFrom-Json
$current = $manifest.version
if (-not $current) { throw "No 'version' field found in manifest.json" }

if ($Version) {
    if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Version must be X.Y.Z" }
    $new = $Version
} else {
    if ($current -notmatch '^\d+\.\d+\.\d+$') { throw "Current version '$current' is not X.Y.Z; pass -Version explicitly" }
    $parts = $current.Split("."); [int]$major = $parts[0]; [int]$minor = $parts[1]; [int]$patch = $parts[2]
    switch ($Bump) { "major" { $major++; $minor = 0; $patch = 0 } "minor" { $minor++; $patch = 0 } "patch" { $patch++ } }
    $new = "$major.$minor.$patch"
}
if ($new -eq $current) { throw "New version matches current version" }

$dirty = git -C $RepoRoot status --porcelain
if ($dirty) { throw "Working tree is not clean:`n$dirty" }

# Update the version in manifest.json, preserving formatting via a targeted replace.
$pattern = '("version"\s*:\s*")' + [regex]::Escape($current) + '(")'
$updated = $manifestRaw -replace $pattern, ('${1}' + $new + '${2}')
if ($updated -eq $manifestRaw) { throw "Failed to update version in manifest.json" }
Set-Content -Path $ManifestPath -Value $updated -NoNewline

$tag = "v$new"
git -C $RepoRoot add $ManifestPath
git -C $RepoRoot commit -m "Release $tag"
git -C $RepoRoot tag $tag
Write-Host "Bumped $current -> $new and created tag $tag locally."

if (-not $Push) {
    Write-Host "Skipping push (this instance is not connected to GitHub). Re-run with -Push to publish."
    return
}

$branch = git -C $RepoRoot rev-parse --abbrev-ref HEAD
git -C $RepoRoot push $Remote $branch
git -C $RepoRoot push $Remote $tag

if (-not $Release) { return }
$gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $gh) { Write-Warning "gh not found; tag pushed without a GitHub release."; return }
gh release create $tag --title $tag --generate-notes
