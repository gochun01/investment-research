@echo off
chcp 65001 >nul

REM TrackingDaemon 작업 스케줄러 등록
REM 로그인 시 자동 시작 + 실패 시 재시작

schtasks /Create /TN "TrackingDaemon" ^
  /TR "\"C:\Program Files\Python312\python.exe\" \"C:\Users\이미영\Downloads\에이전트\01-New project\tracking\tracking_daemon.py\"" ^
  /SC ONLOGON ^
  /RL HIGHEST ^
  /F

if %ERRORLEVEL% EQU 0 (
    echo [OK] TrackingDaemon 등록 완료
) else (
    echo [FAIL] 등록 실패. 관리자 권한으로 실행해주세요.
)

pause
