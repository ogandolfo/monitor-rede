"""Assistente de configuração, chamado pelo Instalar.bat.

Pergunta os dados do roteador, guarda a senha no Gerenciador de Credenciais do
Windows, cria/atualiza o arquivo .env e (opcionalmente) configura o monitor
para iniciar junto com o Windows.
"""
import getpass
import ipaddress
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def ler(prompt):
    """input() que ignora o caractere invisível (BOM) de alguns terminais."""
    return input(prompt).replace("\ufeff", "").strip()


def linha(titulo=""):
    print()
    print("=" * 64)
    if titulo:
        print(f"  {titulo}")
        print("=" * 64)


def perguntar_sim_nao(pergunta, padrao=False):
    sufixo = "[S/n]" if padrao else "[s/N]"
    while True:
        resp = ler(f"{pergunta} {sufixo}: ").lower()
        if not resp:
            return padrao
        if resp in ("s", "sim", "y", "yes"):
            return True
        if resp in ("n", "nao", "não", "no"):
            return False
        print("  Responda com s (sim) ou n (não).")


def detectar_gateway():
    """IP do roteador principal (gateway padrão) deste PC, ou None."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Sort-Object RouteMetric | "
             "Select-Object -First 1).NextHop"],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip()
        ipaddress.ip_address(out)
        return out
    except Exception:  # noqa: BLE001
        return None


def ler_env():
    valores = {}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in raw and not raw.lstrip().startswith("#"):
                chave, valor = raw.split("=", 1)
                valores[chave.strip()] = valor.strip()
    return valores


def gravar_env(valores):
    linhas = ["# Configuracao do Monitor de Rede (gerado pelo Instalar.bat)"]
    linhas += [f"{k}={v}" for k, v in valores.items() if v]
    ENV_PATH.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def pedir_ip(padrao):
    while True:
        texto = f"IP do roteador [{padrao}]: " if padrao else "IP do roteador: "
        ip = ler(texto) or (padrao or "")
        try:
            ipaddress.ip_address(ip)
            return ip
        except ValueError:
            print("  Isso não parece um IP válido (exemplo: 192.168.15.1).")


def pedir_senha(rotulo):
    while True:
        s1 = getpass.getpass(f"{rotulo} (não aparece enquanto você digita): ")
        if not s1:
            print("  A senha não pode ficar vazia.")
            continue
        if s1 != getpass.getpass("Digite a senha de novo para confirmar: "):
            print("  As senhas não conferem, vamos tentar de novo.")
            continue
        return s1


def configurar_roteador(env):
    linha("PASSO 1 de 2 - Seu roteador")
    print("O monitor faz ping no seu roteador para saber se o problema é na sua")
    print("casa (Wi-Fi/cabo) ou na operadora. Para isso ele precisa do IP dele.")
    print("Se você não sabe, apenas aperte ENTER para usar o que foi detectado.")
    print()
    env["ONT_IP"] = pedir_ip(env.get("ONT_IP") or detectar_gateway() or "192.168.1.1")

    print()
    print("OPCIONAL: ler CPU, memória e tempo ligado do roteador via SSH.")
    print("Testado no modem Wi-Fi 6 da Vivo (MitraStar GPT-2742GX4X5).")
    print("Se o seu roteador é outro ou você não sabe o usuário/senha, responda n.")
    if not perguntar_sim_nao("Configurar o acesso SSH ao roteador?", padrao=bool(env.get("ONT_USER"))):
        print("  Ok, a aba 'ONT (SSH)' vai ficar sem dados. Dá para configurar depois.")
        return

    usuario = ler(f"Usuário SSH do roteador [{env.get('ONT_USER', '')}]: ") or env.get("ONT_USER", "")
    if not usuario:
        print("  Sem usuário, pulando o SSH.")
        return
    senha = pedir_senha("Senha SSH do roteador")

    from .credentials import set_ont_password  # import tardio: precisa do keyring instalado
    set_ont_password(usuario, senha)
    env["ONT_USER"] = usuario
    env.pop("ONT_PASS", None)  # a senha não fica mais em texto no .env
    print("  Senha guardada no Gerenciador de Credenciais do Windows (não fica em arquivo).")


def configurar_inicializacao():
    linha("PASSO 2 de 2 - Iniciar junto com o Windows")
    print("Recomendado: assim o monitor grava o histórico o tempo todo, em segundo")
    print("plano e sem janela, mesmo que você não abra o painel.")
    if not perguntar_sim_nao("Iniciar o monitor sozinho quando o Windows ligar?", padrao=True):
        print("  Ok. Para abrir quando quiser, dê dois cliques em Executar_Monitor.bat.")
        return False
    script = ROOT / "scripts" / "autostart.ps1"
    ok = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
         "-Acao", "instalar"],
    ).returncode == 0
    if ok:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Start-ScheduledTask -TaskName 'Monitor de Rede (NetMon)'"])
        print("  Monitor iniciado em segundo plano.")
    else:
        print("  Não consegui configurar. Você pode tentar depois com Iniciar_com_Windows.bat.")
    return ok


def main():
    linha("Monitor de Rede - Configuração")
    print("Vou fazer 2 perguntas rápidas. Em cada uma, o valor entre [colchetes]")
    print("é usado se você só apertar ENTER.")

    env = ler_env()
    configurar_roteador(env)
    gravar_env(env)

    iniciou = configurar_inicializacao()

    linha("PRONTO!")
    if iniciou:
        print("O monitor já está rodando. Abra no navegador:  http://localhost:8501")
        print("(aguarde uns 10 segundos na primeira vez)")
    else:
        print("Para abrir o monitor, dê dois cliques em  Executar_Monitor.bat")
    print()
    print("Se o Windows perguntar sobre o Firewall, permita 'Redes privadas'.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nConfiguração cancelada.")
        sys.exit(1)
