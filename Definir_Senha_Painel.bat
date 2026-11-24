@echo off
title Monitor de Rede - Senha do painel
cd /d "%~dp0"
echo Define a senha pedida quando o painel e aberto de OUTRO aparelho (ex.: celular).
echo Neste PC o painel continua abrindo sem senha.
echo A senha fica guardada (como hash) no Gerenciador de Credenciais do Windows.
echo.
python -m netmon.credentials painel
pause
