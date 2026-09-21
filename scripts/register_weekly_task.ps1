# One-time setup: registers a Windows Task Scheduler task that runs the
# watchlist tracker every Monday. Run this once from a normal PowerShell
# prompt (no elevation needed - this registers a per-user task).
#
# To change the day/time later, edit the trigger via Task Scheduler's GUI,
# or re-run this script after editing $Day / $Time below.
# To remove it: Unregister-ScheduledTask -TaskName "IMDbWatchTrackerWeeklyUpdate"

$ErrorActionPreference = "Stop"

$Day = "Monday"
$Time = "9:00AM"
$TaskName = "IMDbWatchTrackerWeeklyUpdate"

$repoRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $repoRoot "scripts\run_weekly_update.bat"

if (-not (Test-Path $scriptPath)) {
    throw "Could not find $scriptPath - run this script from inside the repo."
}

$action = New-ScheduledTaskAction -Execute $scriptPath
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $Time
# StartWhenAvailable: if the PC was off/asleep at the scheduled time, run
# as soon as it's next available instead of skipping the run entirely.
# WakeToRun: actually wake a sleeping (not powered off) PC to run on time.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun

Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description "Weekly refresh of the IMDb watchlist tracker spreadsheet." `
    -Force | Out-Null

Write-Output "Registered scheduled task '$TaskName': runs every $Day at $Time."
Write-Output ("Logs land in: " + $repoRoot + "\logs\weekly_update.log")
Write-Output ""
Write-Output "Useful commands:"
Write-Output "  Get-ScheduledTask -TaskName $TaskName          # check it's registered"
Write-Output "  Start-ScheduledTask -TaskName $TaskName        # run it right now, manually"
Write-Output "  Get-ScheduledTaskInfo -TaskName $TaskName      # see last run time/result"
Write-Output "  Unregister-ScheduledTask -TaskName $TaskName   # remove it"
