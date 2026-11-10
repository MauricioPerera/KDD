param(
    [Parameter(Mandatory)][string] $Trace,
    [Parameter(Mandatory)][string] $Evidence
)
$ErrorActionPreference = 'Stop'
$profile = Get-Content -Raw -LiteralPath $Evidence | ConvertFrom-Json -AsHashtable
$starts = @{}
$stops = @{}
$children = @{}
$pidMap = @{}
Get-WinEvent -Path $Trace -Oldest | ForEach-Object {
    if ($_.ProviderName -ne 'Microsoft-Windows-Kernel-Process' -or $_.Id -notin 1,2) { return }
    $xml = [xml]$_.ToXml()
    $fields = @{}
    foreach ($item in $xml.Event.EventData.Data) { $fields[$item.Name] = $item.'#text' }
    $seq = [string]$fields.ProcessSequenceNumber
    if (!$seq) { return }
    if ($_.Id -eq 2) {
        if ($fields.ContainsKey('CPUCycleCount')) { $stops[$seq] = [uint64]$fields.CPUCycleCount }
        return
    }
    $parent = [string]$fields.ParentProcessSequenceNumber
    $pidKey = [string]$fields.ProcessID
    $starts[$seq] = @{time=$_.TimeCreated.ToUniversalTime(); image=[IO.Path]::GetFileName($fields.ImageName).ToLowerInvariant()}
    if (!$children.ContainsKey($parent)) { $children[$parent] = [Collections.Generic.List[string]]::new() }
    $children[$parent].Add($seq)
    if (!$pidMap.ContainsKey($pidKey)) { $pidMap[$pidKey] = [Collections.Generic.List[string]]::new() }
    $pidMap[$pidKey].Add($seq)
}
foreach ($name in $profile.jobs.Keys) {
    $job = $profile.jobs[$name]
    $anchor = [datetimeoffset]::FromUnixTimeMilliseconds([long]($job.assigned_epoch * 1000)).UtcDateTime
    $root = $pidMap[[string]$job.root_pid] | Where-Object {
        $starts[$_].image -eq 'python.exe' -and
        [math]::Abs(($anchor-$starts[$_].time).TotalSeconds) -lt 5
    } | Sort-Object { [math]::Abs(($anchor-$starts[$_].time).TotalSeconds) } | Select-Object -First 1
    if (!$root) { throw "No ETW root for $name" }
    $frontier = [Collections.Generic.Queue[string]]::new()
    $frontier.Enqueue($root)
    $metrics = @{git=@{count=0;cycles=[uint64]0};python=@{count=0;cycles=[uint64]0};other=@{count=0;cycles=[uint64]0}}
    $missingStops = 0
    while ($frontier.Count) {
        $seq = $frontier.Dequeue()
        foreach ($child in $children[$seq]) { $frontier.Enqueue($child) }
        $kind = switch -Regex ($starts[$seq].image) {
            '^git\.exe$' {'git'}
            '^python(?:w)?(?:[0-9.]+)?\.exe$' {'python'}
            default {'other'}
        }
        $metrics[$kind].count++
        if ($stops.ContainsKey($seq)) { $metrics[$kind].cycles += $stops[$seq] } else { $missingStops++ }
    }
    $count = $metrics.git.count + $metrics.python.count + $metrics.other.count
    if ($count -ne $job.processes -or $missingStops) {
        throw "Incomplete ETW for $name (tree=$count job=$($job.processes) missing stops=$missingStops)"
    }
    $job.etw = $metrics
}
$profile | ConvertTo-Json -Depth 14 | Set-Content -Encoding utf8 -LiteralPath $Evidence
$profile.jobs | ConvertTo-Json -Depth 6
