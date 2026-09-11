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
  echo.
  echo Nie znaleziono zgodnego Pythona.
  echo Zainstaluj Python 3.13 albo 3.12 64-bit.
  pause
  exit /b 1
)

echo Uzywam: %PY_CMD%
echo.
%PY_CMD% -m pip install --upgrade pip
if errorlevel 1 goto :error

%PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto :error

%PY_CMD% -m pip install pyinstaller
if errorlevel 1 goto :error

echo.
echo Buduje PayCheck.exe...
%PY_CMD% -m PyInstaller --noconfirm --clean --onefile --windowed --name PayCheck app_340.py
if errorlevel 1 goto :error

echo.
echo ========================================
echo GOTOWE
echo Plik EXE:
echo %CD%\dist\PayCheck.exe
echo ========================================
start "" "%CD%\dist"
pause
exit /b 0

:error
echo.
echo BLAD: nie udalo sie zbudowac PayCheck.exe.
echo Przewin wyzej i sprawdz pierwszy komunikat ERROR.
pause
exit /b 1
