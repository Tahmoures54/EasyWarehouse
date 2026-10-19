@echo off
REM Build EasyWarehouse.exe on Windows
cd /d %~dp0\..
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --name EasyWarehouse ^
  --add-data "app\database\schema.sql;app\database" ^
  --add-data "assets;assets" ^
  app\main.py
echo.
echo Output: dist\EasyWarehouse.exe
