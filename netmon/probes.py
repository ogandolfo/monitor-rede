"""Sondas de rede: ping (ICMP), HTTP e métricas da ONT via SSH."""
import re
import subprocess
import time

import paramiko
import requests
import urllib3

from .config import KNOWN_HOSTS_PATH

# Alguns serviços são testados sem validar o certificado (só interessa a disponibilidade)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ----------------------------------------------------------------------
# Ping
# ----------------------------------------------------------------------
_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-:]*$")
# Uma resposta de eco válida sempre traz "TTL=<n>" (pt-BR e en-US). Mensagens como
# "Host de destino inacessível" ou "TTL expirado" não trazem, então contam como perda.
_REPLY_RE = re.compile(r"TTL=\d+", re.IGNORECASE)
_TIME_RE = re.compile(r"(?:tempo|time)\s*([=<])\s*(\d+)\s*ms", re.IGNORECASE)


def ping_host(host, count=3, timeout_ms=1000):
    """Retorna (latência média em ms | None, perda em %)."""
    if not host or not _HOST_RE.match(host):
        return None, 100
    try:
        proc = subprocess.run(
            ["ping", "-n", str(count), "-w", str(timeout_ms), host],
            capture_output=True,
            timeout=count * (timeout_ms / 1000 + 1) + 5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (subprocess.SubprocessError, OSError):
        return None, 100

    # Só nos interessam trechos ASCII, então a página de código do console não importa
    output = proc.stdout.decode("latin-1", errors="ignore")
    times = []
    replies = 0
    for line in output.splitlines():
        if not _REPLY_RE.search(line):
            continue
        replies += 1
        m = _TIME_RE.search(line)
        if m:
            value = float(m.group(2))
            times.append(value / 2 if m.group(1) == "<" else value)  # "<1ms" ≈ 0,5 ms

    loss = round((count - min(replies, count)) * 100 / count)
    latency = round(sum(times) / len(times), 1) if times else None
    return latency, loss


# ----------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------
def check_service(url):
    """Retorna (tempo até a resposta em ms | None, ok, detalhe)."""
    try:
        start = time.perf_counter()
        # stream=True: mede até os cabeçalhos chegarem, sem baixar a página inteira
        with requests.get(url, timeout=(3, 4), headers=HTTP_HEADERS,
                          allow_redirects=True, verify=False, stream=True) as resp:
            elapsed = round((time.perf_counter() - start) * 1000, 1)
            if resp.status_code < 500:
                return elapsed, True, f"HTTP {resp.status_code}"
            return None, False, f"HTTP {resp.status_code}"
    except requests.Timeout:
        return None, False, "Timeout"
    except requests.RequestException:
        return None, False, "Indisponível"


# ----------------------------------------------------------------------
# SSH (ONT)
# ----------------------------------------------------------------------
def format_uptime(seconds_float):
    tot_sec = int(seconds_float)
    days, rem = divmod(tot_sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def _ssh_run(ssh, cmd, timeout=3.0):
    _in, out, _err = ssh.exec_command(cmd, timeout=timeout)
    return out.read().decode(errors="ignore").strip()


def _new_ssh_client():
    """Cliente SSH com a chave da ONT fixada (TOFU).

    Na primeira conexão a chave do roteador é gravada em data/ont_known_hosts.
    Depois disso, se a chave mudar (outro aparelho se passando pela ONT, ou ONT
    resetada/trocada), a conexão é recusada.
    """
    KNOWN_HOSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    KNOWN_HOSTS_PATH.touch(exist_ok=True)
    ssh = paramiko.SSHClient()
    ssh.load_host_keys(str(KNOWN_HOSTS_PATH))
    # AutoAddPolicy só age em hosts ainda desconhecidos; com load_host_keys ela grava no arquivo
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return ssh


def fetch_ssh_metrics(ip, username, password, port=22):
    if not ip or not username or not password:
        return {"error": "Credenciais SSH não configuradas (ONT_IP / ONT_USER no .env e a senha)."}

    ssh = _new_ssh_client()
    try:
        ssh.connect(ip, port=port, username=username, password=password,
                    timeout=3.0, banner_timeout=3.0, auth_timeout=5.0,
                    look_for_keys=False, allow_agent=False)

        # 1. Uptime
        uptime_clean = "Indisponível"
        up_out = _ssh_run(ssh, "cat /proc/uptime")
        if up_out:
            try:
                uptime_clean = format_uptime(float(up_out.split()[0]))
            except ValueError:
                uptime_clean = " ".join(up_out.split())
        if uptime_clean == "Indisponível":
            up_out2 = _ssh_run(ssh, "uptime")
            if up_out2 and "forbidden" not in up_out2.lower() and "usage" not in up_out2.lower():
                uptime_clean = up_out2

        # 2. Memória
        mem_pct = None
        mem_out = _ssh_run(ssh, "cat /proc/meminfo")
        m_tot = re.search(r"MemTotal:\s+(\d+)", mem_out)
        m_free = re.search(r"MemFree:\s+(\d+)", mem_out)
        if m_tot and m_free and float(m_tot.group(1)) > 0:
            m_avail = re.search(r"MemAvailable:\s+(\d+)", mem_out)
            total_kb = float(m_tot.group(1))
            if m_avail:
                used_kb = total_kb - float(m_avail.group(1))
            else:
                m_buff = re.search(r"Buffers:\s+(\d+)", mem_out)
                m_cached = re.search(r"^Cached:\s+(\d+)", mem_out, re.MULTILINE)
                used_kb = total_kb - (float(m_free.group(1))
                                      + (float(m_buff.group(1)) if m_buff else 0.0)
                                      + (float(m_cached.group(1)) if m_cached else 0.0))
                if used_kb < 0:
                    used_kb = total_kb - float(m_free.group(1))
            mem_pct = round(used_kb / total_kb * 100, 1)

        # 3. CPU (duas leituras de /proc/stat com 0,5s de intervalo)
        cpu_pct = None
        try:
            c1 = _ssh_run(ssh, "grep '^cpu ' /proc/stat", timeout=2.0)
            time.sleep(0.5)
            c2 = _ssh_run(ssh, "grep '^cpu ' /proc/stat", timeout=2.0)
            p1 = [float(x) for x in c1.split()[1:]]
            p2 = [float(x) for x in c2.split()[1:]]
            if len(p1) >= 4 and len(p2) >= 4:
                idle1 = p1[3] + (p1[4] if len(p1) > 4 else 0)
                idle2 = p2[3] + (p2[4] if len(p2) > 4 else 0)
                diff_total = sum(p2) - sum(p1)
                if diff_total > 0:
                    calc = (diff_total - (idle2 - idle1)) / diff_total * 100
                    cpu_pct = round(max(0.0, min(100.0, calc)), 1)
        except (ValueError, OSError, paramiko.SSHException):
            pass

        return {"Uptime": uptime_clean, "Memoria_Pct": mem_pct, "CPU_Pct": cpu_pct, "error": None}
    except paramiko.BadHostKeyException:
        return {"error": (
            "⚠️ A chave SSH da ONT mudou desde a primeira conexão — conexão recusada por segurança. "
            "Se você resetou ou trocou o roteador, apague o arquivo data/ont_known_hosts e recarregue. "
            "Se não, algo na rede pode estar se passando pelo roteador."
        )}
    except paramiko.AuthenticationException:
        return {"error": "Usuário ou senha incorretos no SSH."}
    except Exception as e:  # noqa: BLE001 — qualquer falha vira mensagem na tela
        return {"error": f"Falha na conexão SSH com {ip}: {e}"}
    finally:
        ssh.close()
