param(
    [Parameter(Mandatory)][string] $Name,
    [Parameter(Mandatory)][string] $Source,
    [Parameter(Mandatory)][string] $Sha
)
$ErrorActionPreference = 'Stop'
$out = Join-Path $env:RUNNER_TEMP ('kdd-resource-evidence/' + $Name)
$trace = Join-Path $env:RUNNER_TEMP ($Name + '.etl')
$session = 'KDDManifestCost-' + $Name
logman start $session -p Microsoft-Windows-Kernel-Process 0x10 5 -nb 32 128 -bs 64 -o $trace -ets
if ($LASTEXITCODE -ne 0) { throw 'Unable to start ETW trace' }
try {
    python (Join-Path $PSScriptRoot 'postinit_process_cost.py') --source $Source --sha $Sha --out $out
    if ($LASTEXITCODE -ne 0) { throw 'Profile run failed' }
} finally {
    logman stop $session -ets
    if ($LASTEXITCODE -ne 0) { throw 'Unable to flush ETW trace' }
}
& (Join-Path $PSScriptRoot 'collect_process_cost.ps1') -Trace $trace -Evidence (Join-Path $out 'profile.json')
