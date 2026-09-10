@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  py -m pip install -r requirements.txt
  py app_full.py
) else (
  python -m pip install -r requirements.txt
  python app_full.py
)

endlocal
