# gitctap installer for Windows.
#
# Copies gitctap.py and gitctap.cmd into a folder of your own account and puts
# that folder on your PATH, so that `gitctap` works in any terminal, in any
# project. It needs no administrator rights and touches nothing else.
#
# Run it from the folder you unpacked:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
#
# To undo it: delete the folder it names at the end, and remove that same folder
# from PATH (Windows search: "environment variables for your account").

$ErrorActionPreference = "Stop"

$source = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$target = if ($env:GITCTAP_PREFIX) { $env:GITCTAP_PREFIX } else { Join-Path $env:LOCALAPPDATA "Programs\gitctap" }

function Fail($message) {
    Write-Host "x $message" -ForegroundColor Red
    exit 1
}

# 1. The files must be here.
foreach ($file in @("gitctap.py", "gitctap.cmd")) {
    if (-not (Test-Path (Join-Path $source $file))) {
        Fail "$file was not found in $source. Run this script from the unpacked gitctap folder."
    }
}

# 2. A real Python 3 must answer. The Microsoft Store placeholders print only
#    the word "Python" without a version, so they are refused here.
$runner = $null
foreach ($candidate in @("py", "python", "python3")) {
    if (-not (Get-Command $candidate -ErrorAction SilentlyContinue)) { continue }
    $answer = ""
    try { $answer = (& $candidate --version 2>&1 | Out-String).Trim() } catch { continue }
    if ($answer -match "Python 3\.(\d+)") {
        if ([int]$Matches[1] -lt 8) {
            Write-Host "! $candidate is $answer, gitctap needs Python 3.8 or newer" -ForegroundColor Yellow
            continue
        }
        $runner = $candidate
        Write-Host "+ $candidate -> $answer"
        break
    }
}
if (-not $runner) {
    Fail "no working Python 3 found. Install `"Python 3.13`" from the Microsoft Store, open a new terminal, then run this again."
}

# 3. Copy the two files.
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item (Join-Path $source "gitctap.py") -Destination $target -Force
Copy-Item (Join-Path $source "gitctap.cmd") -Destination $target -Force
Write-Host "+ installed to $target"

# 4. Put that folder on PATH, once.
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$parts = @()
if ($userPath) { $parts = $userPath.Split(";") | Where-Object { $_ -ne "" } }
if ($parts -contains $target) {
    Write-Host "+ PATH already contains it"
} else {
    $newPath = if ($parts.Count -gt 0) { ($parts + $target) -join ";" } else { $target }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "+ added to your PATH"
}

# 5. Say what to do next. A new terminal is required: PATH is read at startup.
Write-Host ""
Write-Host "done. Close this window, open a new terminal, then run:" -ForegroundColor Green
Write-Host "  gitctap --version"
Write-Host "  gitctap --help"
Write-Host ""
Write-Host "git is needed for pushing. Check it with: git --version"
