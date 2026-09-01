@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Soeger fly
set PYTHONIOENCODING=utf-8
python soeg.py
if errorlevel 1 (
  echo.
  echo   Noget gik galt. Har du koert INSTALLER.bat foerst?
)
echo.
pause
