@echo off
chcp 65001 >nul
title Fjern automatik
echo.
schtasks /Delete /TN "Flyagent - daglig soegning" /F
echo.
echo   Den daglige soegning er slaaet fra.
echo.
pause
