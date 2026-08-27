#Requires -Version 5.1

<#
.SYNOPSIS
    Run the sprint CLI on Windows without setting PYTHONPATH by hand.

.DESCRIPTION
    `python -m sprint` needs scripts/ on PYTHONPATH and needs to run from the
    repo root, so that .github/sprint.yml resolves. On Windows that is easy to
    get wrong -- the bash idiom `PYTHONPATH=scripts python -m sprint` is not
    valid PowerShell, and `python -m .\scripts\sprint\` is not a module name.
    This wrapper does both correctly and forwards everything you pass it.

    It prefers the interpreter of an activated virtual environment, then
    python / python3 on PATH, then the py launcher.

.EXAMPLE
    .\sprint.ps1 validate

.EXAMPLE
    .\sprint.ps1 status

.EXAMPLE
    .\sprint.ps1 promotion --hop dit
#>

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Arguments = @()
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

if (-not $PSScriptRoot) {
    [Console]::Error.WriteLine('error: run sprint.ps1 from its file, not as a pasted snippet')
    exit 1
}

$root       = $PSScriptRoot
$scriptsDir = Join-Path $root 'scripts'
if (-not (Test-Path -LiteralPath (Join-Path $scriptsDir 'sprint') -PathType Container)) {
    [Console]::Error.WriteLine("error: no sprint package at $scriptsDir\sprint")
    [Console]::Error.WriteLine('       rerun the installer against this repo')
    exit 1
}

# An activated venv wins, so the run matches whatever the shell is pointing at.
$exe    = $null
$prefix = @()

if ($env:VIRTUAL_ENV) {
    foreach ($candidate in @('Scripts\python.exe', 'bin/python')) {
        $path = Join-Path $env:VIRTUAL_ENV $candidate
        if (Test-Path -LiteralPath $path -PathType Leaf) { $exe = $path; break }
    }
}
if (-not $exe) {
    foreach ($name in @('python', 'python3')) {
        $found = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue
        if ($found) { $exe = $found.Source; break }
    }
}
if (-not $exe) {
    $launcher = Get-Command 'py' -CommandType Application -ErrorAction SilentlyContinue
    if ($launcher) { $exe = $launcher.Source; $prefix = @('-3') }
}
if (-not $exe) {
    [Console]::Error.WriteLine('error: no Python found (looked for an active venv, python, python3, py)')
    exit 1
}

# Prepend rather than overwrite, and put it back afterwards: this runs in the
# caller's process, so a bare assignment would leak into their whole session.
$previousPythonPath = $env:PYTHONPATH
$separator = [System.IO.Path]::PathSeparator
if ($previousPythonPath) {
    $env:PYTHONPATH = "$scriptsDir$separator$previousPythonPath"
}
else {
    $env:PYTHONPATH = $scriptsDir
}

$code = 1
Push-Location -LiteralPath $root
try {
    & $exe @prefix -m sprint @Arguments
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
    $env:PYTHONPATH = $previousPythonPath
}

exit $code
