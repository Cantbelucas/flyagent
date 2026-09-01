@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Automatisk daglig flysoegning
echo.
echo   ============================================================
echo     Saet agenten til at soege af sig selv hver dag
echo   ============================================================
echo.
echo   Den soeger i baggrunden og aabner KUN rapporten, hvis prisen
echo   er faldet siden sidst. Alt gemmes i mappen resultater.
echo.
set "TID=08:00"
set /p TID="  Hvilket klokkeslaet? [08:00]: "
echo.
schtasks /Create /TN "Flyagent - daglig soegning" /TR "\"%~dp0KOER-STILLE.bat\"" /SC DAILY /ST %TID% /F
if errorlevel 1 (
  echo.
  echo   Kunne ikke oprette opgaven. Proev at hoejreklikke paa filen
  echo   og vaelge "Kor som administrator".
) else (
  echo.
  echo   Klar. Agenten soeger nu hver dag kl. %TID%.
  echo   Computeren skal vaere taendt paa det tidspunkt.
  echo.
  echo   Vil du stoppe det igen, saa koer FJERN-AUTOMATIK.bat
)
echo.
pause
