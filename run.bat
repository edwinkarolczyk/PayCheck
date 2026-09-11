@echo off
setlocal
cd /d "%~dp0"

set "PY_CMD="

py -3.13 -c "import sys" >nul 2>nul
if %errorlevel%==0 set "PY_CMD=py -3.13"

if not defined PY_CMD (
  py -3.12 -c "import sys" >nul 2>nul
  if %errorlevel%==0 set "PY_CMD=py -3.12"
)

if not defined PY_CMD (
  python -c "import sys" >nul 2>nul
  if %errorlevel%==0 set "PY_CMD=python"
)

if not defined PY_CMD (
  echo Nie znaleziono zgodnego Pythona 3.13/3.12.
  pause
  exit /b 1
)

%PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
  echo Nie udalo sie zainstalowac wymaganych bibliotek.
  pause
  exit /b 1
)

%PY_CMD% app_310.py

endlocal
