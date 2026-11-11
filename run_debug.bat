@echo off
cd /d "%~dp0"
set SAYDRAFT_LOG_LEVEL=DEBUG
set SAYDRAFT_LOG_CONSOLE=1
echo Starting Saydraft in debug mode...
echo Logs: %LOCALAPPDATA%\Saydraft\logs\saydraft.log
echo.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m saydraft
) else (
    python -m saydraft
)
echo.
echo Saydraft exited with code %ERRORLEVEL%.
pause
