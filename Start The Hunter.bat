@echo off
rem Starts The Hunter in the background (if it isn't already running) and opens it in the browser.
cd /d "%~dp0"
powershell -NoProfile -Command ^
  "try { Invoke-WebRequest -UseBasicParsing http://localhost:8000/api/settings -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  powershell -NoProfile -Command ^
    "Start-Process -WindowStyle Hidden -FilePath '.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','backend.main:app','--port','8000' -RedirectStandardOutput server.out.log -RedirectStandardError server.log"
  timeout /t 5 /nobreak >nul
)
start "" http://localhost:8000
