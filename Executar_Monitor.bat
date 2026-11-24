@echo off
title Monitor de Rede
cd /d "%~dp0"
echo Iniciando o Monitor de Rede...
python -m streamlit run monitor.py
pause
