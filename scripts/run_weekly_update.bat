@echo off
setlocal
cd /d "%~dp0.."
if not exist logs mkdir logs

echo ============================================== >> logs\weekly_update.log
echo Run started: %DATE% %TIME% >> logs\weekly_update.log
python -m src.main >> logs\weekly_update.log 2>&1
set RESULT=%ERRORLEVEL%
echo Exit code: %RESULT% >> logs\weekly_update.log

exit /b %RESULT%
