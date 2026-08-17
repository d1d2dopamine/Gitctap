@echo off
rem gitctap launcher for Windows.
rem
rem It only finds a Python 3 and hands every argument over to gitctap.py, which
rem sits next to this file. Nothing else happens here.
setlocal

set "SCRIPT=%~dp0gitctap.py"
if not exist "%SCRIPT%" goto :missing

set "RUNNER="
where py >nul 2>nul
if not errorlevel 1 set "RUNNER=py -3"
if not defined RUNNER (
  where python >nul 2>nul
  if not errorlevel 1 set "RUNNER=python"
)
if not defined RUNNER goto :nopython

%RUNNER% "%SCRIPT%" %*
exit /b %errorlevel%

:missing
echo gitctap.py is not next to this launcher. Keep gitctap.cmd and gitctap.py in the same folder.
exit /b 1

:nopython
echo Python 3 was not found. Install "Python 3.13" from the Microsoft Store, then open a new terminal.
exit /b 1
