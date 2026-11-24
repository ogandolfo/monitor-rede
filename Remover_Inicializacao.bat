@echo off
title Monitor de Rede - Remover inicializacao automatica
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\autostart.ps1" -Acao remover
pause
