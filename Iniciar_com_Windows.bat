@echo off
title Monitor de Rede - Inicializacao automatica
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\autostart.ps1" -Acao instalar
echo.
echo Iniciando o monitor agora em segundo plano...
powershell -NoProfile -Command "Start-ScheduledTask -TaskName 'Monitor de Rede (NetMon)'"
pause
