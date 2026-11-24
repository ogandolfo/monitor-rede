# Registra (ou remove) o Monitor de Rede para iniciar com o Windows,
# em segundo plano e sem janela, via Agendador de Tarefas do usuário atual.
#   powershell -ExecutionPolicy Bypass -File scripts\autostart.ps1 -Acao instalar
#   powershell -ExecutionPolicy Bypass -File scripts\autostart.ps1 -Acao remover
param(
    [ValidateSet("instalar", "remover", "status")]
    [string]$Acao = "instalar"
)

$ErrorActionPreference = "Stop"
$TaskName = "Monitor de Rede (NetMon)"
$ProjectDir = Split-Path -Parent $PSScriptRoot

if ($Acao -eq "remover") {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Inicializacao automatica removida."
    } else {
        Write-Host "A tarefa nao estava registrada."
    }
    exit 0
}

if ($Acao -eq "status") {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) { Write-Host "Registrada. Estado: $($t.State)" } else { Write-Host "Nao registrada." }
    exit 0
}

# pythonw.exe = Python sem janela de console
$python = (Get-Command python -ErrorAction Stop).Source
$pythonw = & $python -c "import sys, os; print(os.path.join(os.path.dirname(sys.executable), 'pythonw.exe'))"
if (-not (Test-Path $pythonw)) { throw "pythonw.exe nao encontrado ao lado de $python" }

$action = New-ScheduledTaskAction -Execute $pythonw `
    -Argument "run.py --server.headless true" `
    -WorkingDirectory $ProjectDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Inicia o Monitor de Rede (Streamlit) em segundo plano no logon." -Force | Out-Null

Write-Host "Pronto: o monitor vai iniciar sozinho sempre que voce entrar no Windows."
Write-Host "Painel: http://localhost:8501"
