@echo off
rem Stops the background Hunter server (any run in progress stops too).
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*uvicorn backend.main*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo The Hunter stopped.
timeout /t 2 >nul
