[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Script,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs = @()
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$scriptPath = [IO.Path]::GetFullPath((Join-Path $repoRoot $Script))
$repoPrefix = $repoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar

if (-not $scriptPath.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Script path escapes the repository root: $Script"
}
if (-not [IO.File]::Exists($scriptPath)) {
    throw "Script not found: $scriptPath"
}

$candidates = [Collections.Generic.List[string]]::new()
$git = Get-Command git.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if ($git) {
    $gitRoot = Split-Path (Split-Path $git.Source -Parent) -Parent
    $candidates.Add((Join-Path $gitRoot 'usr\bin\bash.exe'))
    $candidates.Add((Join-Path $gitRoot 'bin\bash.exe'))
}
if ($env:ProgramFiles) {
    $candidates.Add((Join-Path $env:ProgramFiles 'Git\usr\bin\bash.exe'))
}
Get-Command bash.exe -All -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Source -match '\\(?:Git|PortableGit)\\(?:usr\\bin|bin)\\bash\.exe$' -and
        $_.Source -notmatch '\\Microsoft\\WindowsApps\\bash\.exe$'
    } |
    ForEach-Object { $candidates.Add($_.Source) }

$bash = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -Unique -First 1
if (-not $bash) {
    throw 'Git Bash was not found. Install Git for Windows or run the shell scripts directly from a Bash host.'
}

function ConvertTo-MsysPath([string]$Path) {
    $normalized = $Path.Replace('\', '/')
    if ($normalized -match '^([A-Za-z]):/(.*)$') {
        return '/' + $Matches[1].ToLowerInvariant() + '/' + $Matches[2]
    }
    return $normalized
}

function Quote-Bash([string]$Value) {
    $quote = [string][char]39
    $replacement = $quote + '"' + $quote + '"' + $quote
    return $quote + $Value.Replace($quote, $replacement) + $quote
}

$commandParts = [Collections.Generic.List[string]]::new()
$commandParts.Add((Quote-Bash (ConvertTo-MsysPath $scriptPath)))
foreach ($arg in $ScriptArgs) {
    $commandParts.Add((Quote-Bash $arg))
}

& $bash -lc ($commandParts -join ' ')
exit $LASTEXITCODE
