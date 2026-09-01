@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if not exist "resultater" mkdir "resultater"
python soeg.py --stille >> "resultater\log.txt" 2>&1
