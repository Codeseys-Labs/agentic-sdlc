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
        $decodedArgs = @(ConvertFrom-Json -InputObject $TaskArgsJson)
    } catch {
        throw "TaskArgsJson must be a JSON array: $($_.Exception.Message)"
    }
}
if ($null -eq $decodedArgs -or $decodedArgs -isnot [System.Array]) {
    throw 'TaskArgsJson must be a JSON array.'
}
foreach ($argument in $decodedArgs) {
    if ($null -eq $argument) {
        throw 'TaskArgsJson cannot contain null values.'
    }
    $taskArgs.Add([string]$argument)
}

$arguments = [Collections.Generic.List[string]]::new()
$arguments.Add('--cd')
$arguments.Add($resolvedRoot)
$arguments.Add('run')
$arguments.Add($Task)
foreach ($argument in $taskArgs) {
    $arguments.Add($argument)
}

& $mise.Source @arguments
exit $LASTEXITCODE
