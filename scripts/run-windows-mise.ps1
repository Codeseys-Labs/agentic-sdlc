[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$RepoRoot,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Task,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$TaskArgsJson
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$resolvedRoot = [IO.Path]::GetFullPath($RepoRoot)
$miseFile = Join-Path $resolvedRoot 'mise.toml'
if (-not (Test-Path -LiteralPath $miseFile -PathType Leaf)) {
    throw "mise.toml was not found in native repository path: $resolvedRoot"
}

$mise = Get-Command mise.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $mise) {
    $mise = Get-Command mise -ErrorAction SilentlyContinue | Select-Object -First 1
}
if (-not $mise) {
    throw 'mise was not found on the native Windows PATH. Install mise for Windows before running an all-host task.'
}

$taskArgs = [Collections.Generic.List[string]]::new()
if ($TaskArgsJson.Trim() -eq '[]') {
    $decodedArgs = @()
} else {
    try {
        $decodedArgs = ConvertFrom-Json -InputObject $TaskArgsJson
    } catch {
        throw "TaskArgsJson must be a JSON array: $($_.Exception.Message)"
    }
}
if ($null -eq $decodedArgs) {
    throw 'TaskArgsJson must be a JSON array.'
}
if ($decodedArgs -is [System.Array]) {
    $decodedArgs = @($decodedArgs)
} else {
    # ConvertFrom-Json unwraps a one-element JSON array; restore that sole argument without
    # accepting a non-array object or null.
    if ($TaskArgsJson.Trim() -notmatch '^\s*\[\s*"') {
        throw 'TaskArgsJson must be a JSON array.'
    }
    $decodedArgs = @($decodedArgs)
}
foreach ($argument in $decodedArgs) {
    if ($null -eq $argument) {
        throw 'TaskArgsJson cannot contain null values.'
    }
    $taskArgs.Add([string]$argument)
}

$nodeRoot = & $mise.Source '--no-config' 'where' 'node@22.22.3'
$nodeStatus = $LASTEXITCODE
if ($nodeStatus -ne 0 -or -not $nodeRoot) {
    throw 'The exact Node 22.22.3 root could not be resolved by mise --no-config where.'
}
$node = Join-Path $nodeRoot.Trim() 'node.exe'
if (-not (Test-Path -LiteralPath $node -PathType Leaf)) {
    throw "The exact Node executable is unavailable: $node"
}

# Establish cleanup before setup. This wrapper preserves the direct child exit status rather
# than allowing PowerShell cleanup or later commands to overwrite it.
$cleanup = { }
$childStatus = 2
try {
    $target = $resolvedRoot
    $arguments = [Collections.Generic.List[string]]::new()
    $arguments.Add('--cd')
    $arguments.Add($target)
    $arguments.Add('run')
    $arguments.Add($Task)
    foreach ($argument in $taskArgs) {
        $arguments.Add($argument)
    }
    & $mise.Source @arguments
    $childStatus = $LASTEXITCODE
} finally {
    & $cleanup
}
exit $childStatus
