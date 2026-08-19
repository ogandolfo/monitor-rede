import os
import time
import datetime
import re
import subprocess
import urllib3
from concurrent.futures import ThreadPoolExecutor

import streamlit as st
import pandas as pd
import requests
import paramiko
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

# Carrega variáveis do arquivo .env (se existir)
load_dotenv()

# Desabilita avisos de SSL não verificado para testes HTTPS brutos
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="Monitor de Rede - Windows", layout="wide", page_icon="🌐")

st.markdown("""
    <style>
    div[data-testid="stVerticalBlock"] > div { opacity: 1 !important; }
    .metric-card {
        background-color: #1e1e2e;
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 10px;
        border-left: 5px solid #6c757d;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .metric-card-green { border-left-color: #28a745 !important; }
    .metric-card-orange { border-left-color: #fd7e14 !important; }
    .metric-card-red { border-left-color: #dc3545 !important; }
    
    .card-title { font-size: 0.85rem; color: #a6adc8; font-weight: 600; margin-bottom: 4px; }
    .card-value { font-size: 1.4rem; font-weight: bold; color: #cdd6f4; }
    .card-badge { font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 12px; display: inline-block; margin-top: 4px; }
    .badge-green { background-color: rgba(40, 167, 69, 0.2); color: #28a745; }
    .badge-orange { background-color: rgba(253, 126, 20, 0.2); color: #fd7e14; }
    .badge-red { background-color: rgba(220, 53, 69, 0.2); color: #dc3545; }
    </style>
""", unsafe_allow_html=True)

st.title("🌐 Monitor de Rede & Latência (v25)")

# Auto-refresh global de 15s ativado constantemente
st_autorefresh(interval=15000, limit=None, key="global_autorefresh")

# ----------------------------------------------------
# 1. FUNÇÕES DE SUPORTE E REDE
# ----------------------------------------------------

def get_icmp_stats(target, count=3):
    host = target["ip"]
    name = target["name"]
    icon = target["icon"]
    try:
        cmd = f"ping -n {count} -w 1000 {host}"
        process = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='cp850', errors='ignore')
        output = " ".join(process.stdout.splitlines())

        if not output or ("Estatísticas" not in output and "statistics" not in output):
            return {"Nome": name, "Host": host, "Icone": icon, "Latência (ms)": None, "Perda (%)": 100}

        loss_match = re.search(r'(\d+)%\s*(?:de\s*)?(?:perda|loss)', output, re.IGNORECASE)
        packet_loss = int(loss_match.group(1)) if loss_match else 100

        avg_match = re.search(r'(?:Média|Average)\s*=\s*(\d+)ms', output, re.IGNORECASE)
        avg_latency = float(avg_match.group(1)) if avg_match else None

        return {"Nome": name, "Host": host, "Icone": icon, "Latência (ms)": avg_latency, "Perda (%)": packet_loss}
    except Exception:
        return {"Nome": name, "Host": host, "Icone": icon, "Latência (ms)": None, "Perda (%)": 100}


def check_service(service_info):
    name = service_info["name"]
    url = service_info["url"]
    icon = service_info["icon"]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    try:
        start = time.time()
        response = requests.get(url, timeout=4.0, headers=headers, allow_redirects=True, verify=False)
        elapsed = round((time.time() - start) * 1000, 2)
        status_ok = response.status_code < 500
        return {
            "Serviço": name,
            "Icone": icon,
            "Status": "🟢 Operacional" if status_ok else f"🔴 HTTP {response.status_code}",
            "Tempo de Resposta (ms)": elapsed if status_ok else None,
            "Perda (%)": 0 if status_ok else 100,
            "is_ok": status_ok
        }
    except Exception:
        return {
            "Serviço": name,
            "Icone": icon,
            "Status": "🔴 Indisponível",
            "Tempo de Resposta (ms)": None,
            "Perda (%)": 100,
            "is_ok": False
        }


def format_uptime(seconds_float):
    tot_sec = int(seconds_float)
    days = tot_sec // 86400
    hours = (tot_sec % 86400) // 3600
    minutes = (tot_sec % 3600) // 60
    seconds = tot_sec % 60
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0 or days > 0: parts.append(f"{hours}h")
    if minutes > 0 or hours > 0 or days > 0: parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


@st.cache_data(ttl=120)
def fetch_ssh_metrics(ip, username, password, port=22):
    if not ip or not username or not password:
        return {"error": "Credenciais SSH não configuradas."}

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ip, port=port, username=username, password=password, timeout=3.0, banner_timeout=3.0)

        # 1. Uptime
        uptime_clean = "Indisponível"
        _in, stdout_up, _err = ssh.exec_command("cat /proc/uptime", timeout=3.0)
        up_out = stdout_up.read().decode().strip()

        if up_out:
            try:
                seconds = float(up_out.split()[0])
                uptime_clean = format_uptime(seconds)
            except Exception:
                uptime_clean = " ".join(up_out.split())

        if uptime_clean == "Indisponível":
            _in, stdout_up2, _err = ssh.exec_command("uptime", timeout=3.0)
            up_out2 = stdout_up2.read().decode().strip()
            if up_out2 and "forbidden" not in up_out2.lower() and "usage" not in up_out2.lower():
                uptime_clean = up_out2

        # 2. Memória
        mem_pct = 0.0
        mem_clean_str = "N/A"
        _in, stdout_mem, _err = ssh.exec_command("cat /proc/meminfo", timeout=3.0)
        mem_out = stdout_mem.read().decode().strip()

        if mem_out and "MemTotal" in mem_out:
            m_tot = re.search(r"MemTotal:\s+(\d+)", mem_out)
            m_free = re.search(r"MemFree:\s+(\d+)", mem_out)
            m_buff = re.search(r"Buffers:\s+(\d+)", mem_out)
            m_cached = re.search(r"^Cached:\s+(\d+)", mem_out, re.MULTILINE)

            if m_tot and m_free:
                total_kb = float(m_tot.group(1))
                free_kb = float(m_free.group(1))
                buff_kb = float(m_buff.group(1)) if m_buff else 0.0
                cached_kb = float(m_cached.group(1)) if m_cached else 0.0

                used_kb = total_kb - (free_kb + buff_kb + cached_kb)
                if used_kb < 0:
                    used_kb = total_kb - free_kb

                mem_pct = round((used_kb / total_kb) * 100, 1)
                mem_clean_str = f"{mem_pct}%"

        # 3. CPU
        cpu_pct = 0.0
        cpu_clean_str = "N/A"
        try:
            _in, stdout_c1, _err = ssh.exec_command("cat /proc/stat | grep 'cpu '", timeout=2.0)
            c1_raw = stdout_c1.read().decode().strip()
            time.sleep(0.2)
            _in, stdout_c2, _err = ssh.exec_command("cat /proc/stat | grep 'cpu '", timeout=2.0)
            c2_raw = stdout_c2.read().decode().strip()

            if c1_raw and c2_raw:
                p1 = [float(x) for x in c1_raw.split()[1:]]
                p2 = [float(x) for x in c2_raw.split()[1:]]

                idle1 = p1[3] + (p1[4] if len(p1) > 4 else 0)
                idle2 = p2[3] + (p2[4] if len(p2) > 4 else 0)

                total1 = sum(p1)
                total2 = sum(p2)

                diff_total = total2 - total1
                diff_idle = idle2 - idle1

                if diff_total > 0:
                    calc_cpu = ((diff_total - diff_idle) / diff_total) * 100
                    cpu_pct = round(max(0.0, min(100.0, calc_cpu)), 1)
                    cpu_clean_str = f"{cpu_pct}%"
        except Exception:
            cpu_clean_str = "N/A"

        ssh.close()
        return {
            "Uptime": uptime_clean,
            "Memoria_Pct": mem_pct,
            "Memoria_Str": mem_clean_str,
            "CPU_Pct": cpu_pct,
            "CPU_Str": cpu_clean_str,
            "error": None
        }
    except paramiko.AuthenticationException:
        ssh.close()
        return {"error": "Usuário ou senha incorretos no SSH."}
    except Exception as e:
        ssh.close()
        return {"error": f"Falha na conexão SSH com {ip}: {e}"}


# ----------------------------------------------------
# 2. INTERFACE EM ABAS
# ----------------------------------------------------

tab1, tab2, tab3 = st.tabs([
    "⚡ Latência Externa & DNS Públicos", 
    "🌐 Status de Serviços Web, Redes, Streaming & Games",
    "📡 Métricas ONT MitraStar (SSH)"
])

# ====================================================
# ABA 1: ICMP / Ping Externa em DNS Públicos
# ====================================================
with tab1:
    st.subheader("⚡ Monitoramento de Latência DNS públicos (15s)")
    gateway_ip = os.getenv("ONT_IP", "192.168.1.1")
    
    dns_targets = [
        {"name": "Cloudflare Pri.", "ip": "1.1.1.1", "icon": "⚡"},
        {"name": "Google DNS Pri.", "ip": "8.8.8.8", "icon": "🌐"},
        {"name": "Quad9 Primary", "ip": "9.9.9.9", "icon": "🛡️"},
        {"name": "OpenDNS Pri.", "ip": "208.67.222.222", "icon": "🔓"},
        {"name": "AdGuard DNS", "ip": "94.140.14.14", "icon": "🛡️"},
        {"name": "Cloudflare Sec.", "ip": "1.0.0.1", "icon": "⚡"},
        {"name": "Google DNS Sec.", "ip": "8.8.4.4", "icon": "🌐"},
        {"name": "Quad9 Secondary", "ip": "149.112.112.112", "icon": "🛡️"},
        {"name": "OpenDNS Sec.", "ip": "208.67.220.220", "icon": "🔓"},
        {"name": "Gateway", "ip": gateway_ip, "icon": "🖧"}
    ]

    with ThreadPoolExecutor(max_workers=len(dns_targets)) as executor:
        current_results = list(executor.map(get_icmp_stats, dns_targets))

    cols_dns = st.columns(5)
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    new_entry_lat, new_entry_loss = {"Horário": now_str}, {"Horário": now_str}

    for idx, res in enumerate(current_results):
        loss, lat = res["Perda (%)"], res["Latência (ms)"]
        lat_text = f"{lat:.0f} ms" if lat is not None else "Offline"
        
        if loss == 0:
            card_class = "metric-card-green"
            badge_class = "badge-green"
            status_icon = "🟢"
        elif loss <= 5:
            card_class = "metric-card-orange"
            badge_class = "badge-orange"
            status_icon = "🟠"
        else:
            card_class = "metric-card-red"
            badge_class = "badge-red"
            status_icon = "🔴"

        with cols_dns[idx % 5]:
            st.markdown(f"""
                <div class="metric-card {card_class}">
                    <div class="card-title">{res['Icone']} {res['Nome']}</div>
                    <div class="card-value">{lat_text}</div>
                    <div class="card-badge {badge_class}">{status_icon} {loss}% Perda</div>
                </div>
            """, unsafe_allow_html=True)
        
        new_entry_lat[res["Nome"]] = lat
        new_entry_loss[res["Nome"]] = loss

    if "ping_history" not in st.session_state:
        st.session_state.ping_history = pd.DataFrame(columns=["Horário"] + [t["name"] for t in dns_targets])
        st.session_state.ping_loss_history = pd.DataFrame(columns=["Horário"] + [t["name"] for t in dns_targets])

    st.session_state.ping_history = pd.concat([st.session_state.ping_history, pd.DataFrame([new_entry_lat])], ignore_index=True).tail(120)
    st.session_state.ping_loss_history = pd.concat([st.session_state.ping_loss_history, pd.DataFrame([new_entry_loss])], ignore_index=True).tail(120)

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("📊 Latência (ms) - Últimos 30 min")
        st.line_chart(st.session_state.ping_history.set_index("Horário"))
    with col_g2:
        st.subheader("📉 Perda de Pacotes (%) - Últimos 30 min")
        st.line_chart(st.session_state.ping_loss_history.set_index("Horário"))

# ====================================================
# ABA 2: Checagem Completa de Serviços Web
# ====================================================
with tab2:
    st.subheader("🌐 Disponibilidade & Latência HTTP: Web, Redes, Streaming & Games (15s)")

    services_list = [
        {"name": "Serasa Consumidor", "url": "https://www.serasa.com.br", "icon": "💳"},
        {"name": "Serasa Experian", "url": "https://www.serasaexperian.com.br", "icon": "🏢"},
        {"name": "WhatsApp Web", "url": "https://www.whatsapp.com", "icon": "💬"},
        {"name": "Instagram", "url": "https://www.instagram.com", "icon": "📸"},
        {"name": "Twitter / X", "url": "https://x.com", "icon": "🐦"},
        {"name": "Facebook CDN", "url": "https://www.facebook.com", "icon": "📘"},
        {"name": "TikTok", "url": "https://www.tiktok.com", "icon": "🎵"},
        {"name": "Reddit", "url": "https://www.reddit.com", "icon": "🤖"},
        {"name": "Discord API", "url": "https://discord.com", "icon": "💬"},
        {"name": "Netflix CDN", "url": "https://assets.nflxext.com", "icon": "🍿"},
        {"name": "Prime Video", "url": "https://www.primevideo.com", "icon": "🎬"},
        {"name": "Disney+", "url": "https://www.disneyplus.com", "icon": "🏰"},
        {"name": "Max (HBO)", "url": "https://auth.max.com", "icon": "🎭"},
        {"name": "YouTube Video", "url": "https://www.youtube.com/generate_204", "icon": "▶️"},
        {"name": "Twitch Stream", "url": "https://www.twitch.tv", "icon": "🟣"},
        {"name": "Spotify Web", "url": "https://open.spotify.com", "icon": "🟢"},
        {"name": "League of Legends", "url": "https://br1.api.riotgames.com/lol/status/v4/platform-data", "icon": "⚔️"},
        {"name": "Steam Web API", "url": "https://api.steampowered.com/ISteamWebAPIUtil/GetServerInfo/v0001/", "icon": "🎮"},
        {"name": "Xbox Live API", "url": "https://www.xbox.com", "icon": "🟢"},
        {"name": "PlayStation Network", "url": "https://auth.api.sonyentertainmentnetwork.com", "icon": "🔷"}
    ]

    with ThreadPoolExecutor(max_workers=len(services_list)) as executor:
        services_results = list(executor.map(check_service, services_list))

    cols_srv = st.columns(5)
    now_srv = datetime.datetime.now().strftime("%H:%M:%S")
    new_srv_lat = {"Horário": now_srv}
    new_srv_loss = {"Horário": now_srv}

    for idx, srv in enumerate(services_results):
        ms_val = srv["Tempo de Resposta (ms)"]
        ms_text = f"{ms_val:.0f} ms" if ms_val is not None else "Falha"
        
        if srv["is_ok"]:
            card_class = "metric-card-green"
            badge_class = "badge-green"
            status_txt = "🟢 Online"
        else:
            card_class = "metric-card-red"
            badge_class = "badge-red"
            status_txt = "🔴 Queda"

        with cols_srv[idx % 5]:
            st.markdown(f"""
                <div class="metric-card {card_class}">
                    <div class="card-title">{srv['Icone']} {srv['Serviço']}</div>
                    <div class="card-value">{ms_text}</div>
                    <div class="card-badge {badge_class}">{status_txt}</div>
                </div>
            """, unsafe_allow_html=True)

        new_srv_lat[srv["Serviço"]] = ms_val
        new_srv_loss[srv["Serviço"]] = srv["Perda (%)"]

    if "services_history" not in st.session_state:
        st.session_state.services_history = pd.DataFrame(columns=["Horário"] + [s["name"] for s in services_list])
        st.session_state.services_loss_history = pd.DataFrame(columns=["Horário"] + [s["name"] for s in services_list])

    st.session_state.services_history = pd.concat([st.session_state.services_history, pd.DataFrame([new_srv_lat])], ignore_index=True).tail(120)
    st.session_state.services_loss_history = pd.concat([st.session_state.services_loss_history, pd.DataFrame([new_srv_loss])], ignore_index=True).tail(120)

    col_sg1, col_sg2 = st.columns(2)
    with col_sg1:
        st.subheader("📊 Latência dos Serviços (ms) - Últimos 30 min")
        st.line_chart(st.session_state.services_history.set_index("Horário"))
    with col_sg2:
        st.subheader("📉 Perda de Pacotes (%) - Últimos 30 min")
        st.line_chart(st.session_state.services_loss_history.set_index("Horário"))

# ====================================================
# ABA 3: Consulta CLI MitraStar via SSH
# ====================================================
with tab3:
    st.subheader("📡 Informações do Roteador MitraStar (Coleta automática a cada 120s)")
    
    # Valores padrão puxados com segurança do .env
    env_ip = os.getenv("ONT_IP", "")
    env_user = os.getenv("ONT_USER", "")
    env_pass = os.getenv("ONT_PASS", "")

    col_ssh_1, col_ssh_2, col_ssh_3 = st.columns(3)
    with col_ssh_1:
        ssh_ip = st.text_input("IP da ONT", env_ip)
    with col_ssh_2:
        ssh_user = st.text_input("Usuário SSH", env_user)
    with col_ssh_3:
        ssh_pass = st.text_input("Senha SSH", env_pass, type="password", key="ssh_password_input")

    data = fetch_ssh_metrics(ssh_ip, ssh_user, ssh_pass)

    if data.get("error"):
        st.error(f"🔴 {data['error']}")
    else:
        st.success("🟢 Conectado e atualizado via SSH!")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("⏱️ Uptime (Tempo Online)", data["Uptime"])
        with c2:
            st.metric("🧠 Uso de Memória RAM", data["Memoria_Str"])
            if isinstance(data.get("Memoria_Pct"), (int, float)):
                st.progress(data["Memoria_Pct"] / 100.0)
        with c3:
            st.metric("⚡ Uso do Processador (CPU)", data["CPU_Str"])
            if isinstance(data.get("CPU_Pct"), (int, float)):
                st.progress(data["CPU_Pct"] / 100.0)

        # Controle de gravação do histórico a cada 2 minutos
        if "ssh_history" not in st.session_state:
            st.session_state.ssh_history = pd.DataFrame(columns=["Horário", "CPU (%)", "RAM (%)"])

        now_ssh = datetime.datetime.now().strftime("%H:%M:%S")
        cpu_val = data.get("CPU_Pct", 0)
        ram_val = data.get("Memoria_Pct", 0)

        last_time = st.session_state.get("last_ssh_time", 0)
        current_time = time.time()

        if (current_time - last_time) >= 115:
            if isinstance(cpu_val, (int, float)) and isinstance(ram_val, (int, float)):
                new_ssh_entry = {"Horário": now_ssh, "CPU (%)": cpu_val, "RAM (%)": ram_val}
                st.session_state.ssh_history = pd.concat(
                    [st.session_state.ssh_history, pd.DataFrame([new_ssh_entry])], 
                    ignore_index=True
                ).tail(30)
                st.session_state.last_ssh_time = current_time

        if not st.session_state.ssh_history.empty:
            st.subheader("📊 Histórico de Consumo de Hardware da ONT (Últimas 30 coletas)")
            st.line_chart(st.session_state.ssh_history.set_index("Horário"))