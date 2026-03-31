@echo off
chcp 65001 >nul
schtasks /Create /TN "TrackingDaemon" /TR "\"C:\Program Files\Python312\python.exe\" \"C:\Users\이미영\Downloads\에이전트\01-New project\tracking\tracking_daemon.py\"" /SC ONLOGON /RL HIGHEST /F
if %ERRORLEVEL% EQU 0 (
    echo [OK] TrackingDaemon registered successfully
) else (
    echo [FAIL] Registration failed. Run as Administrator.
)
