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
  echo Nie znaleziono Python 3.13/3.12.
  pause
  exit /b 1
)

%PY_CMD% -m pip install -r requirements.txt
%PY_CMD% -m pip install pyinstaller
if errorlevel 1 goto :error

%PY_CMD% -m PyInstaller --noconfirm --clean --onefile --windowed --name PayCheck-Owner-Keygen owner_keygen.py
if errorlevel 1 goto :error

echo.
echo GOTOWE: %CD%\dist\PayCheck-Owner-Keygen.exe
start "" "%CD%\dist"
pause
exit /b 0

:error
echo BLAD budowania keygena.
pause
exit /b 1
