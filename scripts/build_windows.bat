@echo off
setlocal
REM Build AnbardariAsan.exe on Windows. Stop immediately if any step fails.
cd /d "%~dp0.."
if errorlevel 1 exit /b 1

python -m venv .venv
if errorlevel 1 exit /b 1
call .venv\Scripts\activate.bat
if errorlevel 1 exit /b 1

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

python -m PyInstaller --noconfirm --clean --onefile --windowed --name AnbardariAsan ^
  --add-data "app\database\schema.sql;app\database" ^
  --add-data "assets;assets" ^
  app\main.py
if errorlevel 1 exit /b 1
if not exist "dist\AnbardariAsan.exe" (
  echo ERROR: dist\AnbardariAsan.exe was not created.
  exit /b 1
)

echo.
echo Build successful: %CD%\dist\AnbardariAsan.exe
exit /b 0
