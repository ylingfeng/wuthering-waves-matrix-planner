param(
    [string]$DesktopPath = [Environment]::GetFolderPath('DesktopDirectory')
)

$ErrorActionPreference = 'Stop'
$plannerRoot = Split-Path -Parent $PSScriptRoot
$plannerDist = Join-Path $plannerRoot 'dist'
$plannerRelease = Get-ChildItem -LiteralPath $plannerDist -Directory |
    Where-Object {
        $_.Name -match '^v\d+\.\d+\.\d+$' -and
        (Test-Path -LiteralPath (Join-Path $_.FullName 'manifest.json')) -and
        (Test-Path -LiteralPath (Join-Path $_.FullName 'Windows/MatrixPlanner/鸣潮矩阵配队.exe')) -and
        (Test-Path -LiteralPath (Join-Path $_.FullName ('MatrixPlanner-Windows-' + $_.Name + '.zip')))
    } |
    Sort-Object { [version]$_.Name.Substring(1) } -Descending |
    Select-Object -First 1
if (-not $plannerRelease) { throw 'No complete Windows release found in dist.' }
if (-not (Test-Path -LiteralPath $DesktopPath -PathType Container)) { throw 'Desktop directory does not exist.' }

$plannerExe = Join-Path $plannerRelease.FullName 'Windows/MatrixPlanner/鸣潮矩阵配队.exe'
$plannerCheck = Start-Process -FilePath $plannerExe -ArgumentList '--check' -Wait -PassThru -WindowStyle Hidden
if ($plannerCheck.ExitCode -ne 0) { throw 'Release launcher cannot locate its website.' }

$plannerLinkPath = Join-Path $DesktopPath '鸣潮矩阵配队.lnk'
$plannerShell = New-Object -ComObject WScript.Shell
$plannerLink = $plannerShell.CreateShortcut($plannerLinkPath)
$plannerLink.TargetPath = $plannerExe
$plannerLink.WorkingDirectory = Split-Path -Parent $plannerExe
$plannerLink.IconLocation = $plannerExe + ',0'
$plannerLink.Description = '鸣潮矩阵配队 ' + $plannerRelease.Name
$plannerLink.Save()

$plannerSavedLink = $plannerShell.CreateShortcut($plannerLinkPath)
if ($plannerSavedLink.TargetPath -ne $plannerExe) { throw 'Shortcut target verification failed.' }
[pscustomobject]@{
    Version = $plannerRelease.Name
    Shortcut = $plannerLinkPath
    Target = $plannerSavedLink.TargetPath
}
