@echo off
title Monitor de Rede
cd /d "%~dp0"
rem Se o monitor ja estiver rodando (ex.: iniciado com o Windows), so abre o painel
curl -s -o nul -m 2 http://localhost:8501/_stcore/health && (
    echo O monitor ja esta rodando. Abrindo o painel...
    start "" http://localhost:8501
    exit /b
)
echo Iniciando o Monitor de Rede...
python run.py
pause
