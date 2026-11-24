@echo off
chcp 65001 >nul
title Monitor de Rede - Instalacao
cd /d "%~dp0"

echo ================================================================
echo   Monitor de Rede - Instalacao
echo ================================================================
echo.

rem 1) Confere se o Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] O Python nao foi encontrado neste computador.
    echo.
    echo  1. Vou abrir a pagina de download do Python.
    echo  2. Baixe e instale a versao mais recente.
    echo  3. IMPORTANTE: na primeira tela do instalador, marque a caixa
    echo     "Add python.exe to PATH" antes de clicar em "Install Now".
    echo  4. Depois, rode este Instalar.bat de novo.
    echo.
    start "" https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo Python encontrado: %%v
echo.

rem 2) Instala as bibliotecas que o monitor usa
echo Instalando as bibliotecas necessarias (pode levar alguns minutos)...
python -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERRO] Nao consegui instalar as bibliotecas. Confira sua internet e
    echo        rode este Instalar.bat de novo.
    pause
    exit /b 1
)
echo Bibliotecas instaladas.

rem 3) Assistente de configuracao (roteador e inicializacao)
python -m netmon.instalar
echo.
pause
