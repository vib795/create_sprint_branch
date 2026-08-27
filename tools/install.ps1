#Requires -Version 5.1

<#
.SYNOPSIS
    Install (or update) sprint automation in another repository.

.DESCRIPTION
    The Windows counterpart to tools/install.sh. Both installers read
    tools/payload.manifest, so they copy exactly the same files and a repo
    installed from Windows matches one installed from macOS or Linux.

    The payload lives under template/ so this repo never runs the automation on
    itself. Source and destination paths differ, which is what the manifest
    encodes: template/workflows/*.yml lands in .github/workflows/, and
    template/sprint.yml becomes the target repo's .github/sprint.yml.

.EXAMPLE
    .\tools\install.ps1 C:\src\my-repo
    Copy the payload in.

.EXAMPLE
    .\tools\install.ps1 -Check C:\src\my-repo
    Report drift, change nothing. Also accepts --check.

.NOTES
    If PowerShell refuses to run the file, start it this way instead:
        powershell -ExecutionPolicy Bypass -File .\tools\install.ps1 C:\src\my-repo
#>

param(
    [Parameter(Position = 0)]
    [string] $Target,

    [switch] $Check,

    [switch] $Help,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Rest = @()
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- helpers ---

function Write-Usage {
    @'
Install (or update) sprint automation in another repository.

  tools\install.ps1 C:\path\to\repo            copy the payload in
  tools\install.ps1 -Check C:\path\to\repo     report drift, change nothing

--check is accepted as well, for parity with tools/install.sh.
'@ | Write-Host
}

function Fail {
    param([string] $Message)
    [Console]::Error.WriteLine("error: $Message")
    exit 1
}

# The manifest uses forward slashes; Windows takes them, but native separators
# read better in the output a Windows user is looking at.
function ConvertTo-NativePath {
    param([string] $Path)
    return $Path.Replace('/', [string][System.IO.Path]::DirectorySeparatorChar)
}

function Get-PayloadEntries {
    param([string] $ManifestPath)

    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        Fail "payload manifest not found at $ManifestPath"
    }

    $entries = New-Object System.Collections.ArrayList
    foreach ($raw in [System.IO.File]::ReadAllLines($ManifestPath)) {
        $line = $raw
        $comment = $line.IndexOf('#')
        if ($comment -ge 0) { $line = $line.Substring(0, $comment) }
        $line = $line.Trim()          # also drops the CR of a CRLF checkout
        if ($line.Length -eq 0) { continue }

        $split = $line.IndexOf(':')
        if ($split -lt 1 -or $split -eq ($line.Length - 1)) {
            Fail "malformed manifest line (expected source:destination): $line"
        }

        [void] $entries.Add([pscustomobject] @{
            Source      = $line.Substring(0, $split).Trim()
            Destination = $line.Substring($split + 1).Trim()
        })
    }

    if ($entries.Count -eq 0) {
        Fail "payload manifest lists no files: $ManifestPath"
    }
    return $entries
}

function Test-FileMatches {
    param([string] $Expected, [string] $Actual)

    if (-not (Test-Path -LiteralPath $Actual -PathType Leaf)) { return $false }
    $left  = (Get-FileHash -LiteralPath $Expected -Algorithm SHA256).Hash
    $right = (Get-FileHash -LiteralPath $Actual   -Algorithm SHA256).Hash
    return ($left -eq $right)
}

function New-ParentDirectory {
    param([string] $FilePath)
    $parent = Split-Path -Path $FilePath -Parent
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) {
        [void] (New-Item -ItemType Directory -Path $parent -Force)
    }
}

# LF and no BOM, so the stamp file reads identically to the one install.sh
# writes -- Windows PowerShell 5.1 would otherwise emit UTF-8 with a BOM.
function Write-TextFileLf {
    param([string] $Path, [string] $Text)
    New-ParentDirectory -FilePath $Path
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, ($Text -replace "`r`n", "`n"), $utf8NoBom)
}

# Append without rewriting a single existing byte: the target's requirements
# file belongs to that project, not to us.
function Add-RequirementLine {
    param([string] $Path, [string] $Line)

    $existing = [System.IO.File]::ReadAllBytes($Path)
    $prefix = ''
    if ($existing.Length -gt 0 -and $existing[$existing.Length - 1] -ne 0x0A) {
        $prefix = "`n"
    }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($prefix + $Line + "`n")

    $stream = [System.IO.File]::Open(
        $Path, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write)
    try   { $stream.Write($bytes, 0, $bytes.Length) }
    finally { $stream.Close() }
}

function Test-MentionsPyYaml {
    param([string] $Path)
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match '^\s*pyyaml') { return $true }   # -match is case-insensitive
    }
    return $false
}

# ------------------------------------------------------------ arguments ----

$tokens = New-Object System.Collections.ArrayList
if ($Target) { [void] $tokens.Add($Target) }
if ($Rest)   { foreach ($item in $Rest) { if ($item) { [void] $tokens.Add($item) } } }

$checkOnly = [bool] $Check
$wantsHelp = [bool] $Help
$targetPath = $null

# Known switches are matched exactly, and only a leading '-' marks an unknown
# option. Matching a leading '/' as well would swallow POSIX paths, and a
# Windows path never starts with a dash.
foreach ($token in $tokens) {
    switch -Regex ($token) {
        '^(--check|-check|/check)$'      { $checkOnly = $true; continue }
        '^(--help|-help|/help|/\?|-\?)$' { $wantsHelp = $true; continue }
        '^-'                             { Write-Host "unknown option: $token"; Write-Usage; exit 1 }
        default {
            if ($targetPath) {
                Write-Host "unexpected extra argument: $token"
                Write-Usage
                exit 1
            }
            $targetPath = $token
        }
    }
}

if ($wantsHelp) { Write-Usage; exit 0 }

if (-not $targetPath) {
    [Console]::Error.WriteLine('error: no target repository given')
    Write-Usage
    exit 1
}

# ---------------------------------------------------------------- context ---

if (-not $PSScriptRoot) {
    Fail 'cannot resolve the script directory; run install.ps1 from a file, not a pasted snippet'
}

$sourceDir = Split-Path -Path $PSScriptRoot -Parent
$versionFile = Join-Path $sourceDir 'VERSION'
if (-not (Test-Path -LiteralPath $versionFile -PathType Leaf)) {
    Fail "VERSION not found at $versionFile"
}
$version = ([System.IO.File]::ReadAllText($versionFile)).Trim()

$payload = Get-PayloadEntries -ManifestPath (Join-Path $sourceDir 'tools/payload.manifest')

$configSource = 'template/sprint.yml'
$configDest   = '.github/sprint.yml'

if (-not (Test-Path -LiteralPath $targetPath -PathType Container)) {
    Fail "$targetPath is not a directory"
}
# A .git directory for a normal clone; a .git file for a worktree or submodule.
if (-not (Test-Path -LiteralPath (Join-Path $targetPath '.git'))) {
    Fail "$targetPath is not a git repository"
}

$targetDir = (Resolve-Path -LiteralPath $targetPath).ProviderPath
$sourceFull = (Resolve-Path -LiteralPath $sourceDir).ProviderPath
if ($targetDir.TrimEnd('\', '/') -ieq $sourceFull.TrimEnd('\', '/')) {
    Fail 'target is the sprint-automation repo itself'
}

$stamp = Join-Path $targetDir (ConvertTo-NativePath '.github/.sprint-automation-version')

# ------------------------------------------------------------------ check ---

if ($checkOnly) {
    $installed = 'none'
    if (Test-Path -LiteralPath $stamp -PathType Leaf) {
        $installed = ([System.IO.File]::ReadAllText($stamp)).Trim()
    }
    Write-Host "template version:  $version"
    Write-Host "installed version: $installed"

    $drift = 0
    foreach ($entry in $payload) {
        $src  = Join-Path $sourceFull (ConvertTo-NativePath $entry.Source)
        $dest = Join-Path $targetDir  (ConvertTo-NativePath $entry.Destination)
        $shown = ConvertTo-NativePath $entry.Destination

        if (-not (Test-Path -LiteralPath $dest -PathType Leaf)) {
            Write-Host "  MISSING  $shown"
            $drift++
        }
        elseif (-not (Test-FileMatches -Expected $src -Actual $dest)) {
            Write-Host "  DIFFERS  $shown"
            $drift++
        }
    }

    $configShown = ConvertTo-NativePath $configDest
    if (Test-Path -LiteralPath (Join-Path $targetDir (ConvertTo-NativePath $configDest)) -PathType Leaf) {
        Write-Host "  config   $configShown present (never overwritten by this script)"
    }
    else {
        Write-Host "  MISSING  $configShown"
        $drift++
    }

    if ($drift -eq 0) { Write-Host 'up to date' }
    else { Write-Host "$drift file(s) need attention - rerun without -Check" }
    exit 0
}

# ---------------------------------------------------------------- install ---

Write-Host "Installing sprint-automation $version into $targetDir"

foreach ($entry in $payload) {
    $src  = Join-Path $sourceFull (ConvertTo-NativePath $entry.Source)
    $dest = Join-Path $targetDir  (ConvertTo-NativePath $entry.Destination)

    if (-not (Test-Path -LiteralPath $src -PathType Leaf)) {
        Fail "payload file listed in the manifest is missing: $($entry.Source)"
    }
    New-ParentDirectory -FilePath $dest
    Copy-Item -LiteralPath $src -Destination $dest -Force
    Write-Host "  wrote    $(ConvertTo-NativePath $entry.Destination)"
}

# The config carries per-team cadence, so an existing one is never clobbered.
$configTarget = Join-Path $targetDir (ConvertTo-NativePath $configDest)
if (Test-Path -LiteralPath $configTarget -PathType Leaf) {
    Write-Host "  kept     $(ConvertTo-NativePath $configDest) (existing config left untouched)"
}
else {
    New-ParentDirectory -FilePath $configTarget
    Copy-Item -LiteralPath (Join-Path $sourceFull (ConvertTo-NativePath $configSource)) `
              -Destination $configTarget -Force
    Write-Host "  wrote    $(ConvertTo-NativePath $configDest)  <-- set your cadence anchor and branch names"
}

# Merge the runtime dependency rather than replacing a requirements file that
# may already describe the target project.
foreach ($req in @('requirements.txt', 'requirements-dev.txt')) {
    $reqTarget = Join-Path $targetDir $req
    if (-not (Test-Path -LiteralPath $reqTarget -PathType Leaf)) {
        Copy-Item -LiteralPath (Join-Path $sourceFull $req) -Destination $reqTarget -Force
        Write-Host "  wrote    $req"
    }
    elseif (-not (Test-MentionsPyYaml -Path $reqTarget)) {
        if ($req -eq 'requirements.txt') {
            Add-RequirementLine -Path $reqTarget -Line 'PyYAML>=6.0'
            Write-Host "  appended PyYAML>=6.0 to $req"
        }
    }
    else {
        Write-Host "  kept     $req (PyYAML already present)"
    }
}

Write-TextFileLf -Path $stamp -Text "$version`n"

Write-Host ''
Write-Host "Installed. Next, in $targetDir"
Write-Host ''
Write-Host '  1. Edit .github\sprint.yml   - set cadence.anchor to a date your sprint'
Write-Host '                                 started, and branches.base to develop or'
Write-Host '                                 whatever you cut sprints from.'
Write-Host '  2. Confirm the cadence:      $env:PYTHONPATH = "scripts"'
Write-Host '                               python -m sprint validate'
Write-Host '  3. Add a SPRINT_TOKEN secret so promotion pull requests run their checks.'
Write-Host '  4. Commit, then run the "Sprint - cut branch" workflow manually to verify.'
