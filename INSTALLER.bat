@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Installerer flyagenten
echo.
echo   Installerer det agenten skal bruge. Det tager 1-2 minutter.
echo.
python -m pip install --upgrade playwright
if errorlevel 1 (
  echo.
  echo   Python blev ikke fundet. Hent det paa https://www.python.org/downloads/
  echo   og husk at saette flueben i "Add Python to PATH" under installationen.
  echo.
  pause
  exit /b 1
)
python -m playwright install chromium
echo.
echo   Faerdig. Du kan nu koere SOEG-FLY.bat
echo.
pause
