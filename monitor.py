"""Monitor de Rede & Latência — dashboard Streamlit (Windows).

A coleta (ping, HTTP e SSH) roda em threads de fundo compartilhadas por todas
as abas do navegador; a interface apenas lê o estado e se redesenha a cada 5s.
"""
import datetime as dt
import html
import os
import re
import subprocess
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import altair as alt
import pandas as pd
import paramiko
import requests
import streamlit as st
import urllib3
from dotenv import load_dotenv

load_dotenv()

# Alguns serviços são testados sem validar o certificado (só interessa a disponibilidade)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ----------------------------------------------------
# CONFIGURAÇÃO
# ----------------------------------------------------
PROBE_INTERVAL_S = 5          # ping + HTTP
SSH_INTERVAL_S = 120          # métricas da ONT
HISTORY_POINTS = 360          # 360 x 5s = 30 min
SSH_HISTORY_POINTS = 30       # 30 x 120s = 1 h

GATEWAY_IP = os.getenv("ONT_IP", "192.168.1.1")

DNS_TARGETS = [
    {"name": "Cloudflare Pri.", "ip": "1.1.1.1", "icon": "⚡"},
    {"name": "Google DNS Pri.", "ip": "8.8.8.8", "icon": "🌐"},
    {"name": "Quad9 Primary", "ip": "9.9.9.9", "icon": "🛡️"},
    {"name": "OpenDNS Pri.", "ip": "208.67.222.222", "icon": "🔓"},
    {"name": "AdGuard DNS", "ip": "94.140.14.14", "icon": "🛡️"},
    {"name": "Cloudflare Sec.", "ip": "1.0.0.1", "icon": "⚡"},
    {"name": "Google DNS Sec.", "ip": "8.8.4.4", "icon": "🌐"},
    {"name": "Quad9 Secondary", "ip": "149.112.112.112", "icon": "🛡️"},
    {"name": "OpenDNS Sec.", "ip": "208.67.220.220", "icon": "🔓"},
    {"name": "Gateway", "ip": GATEWAY_IP, "icon": "🖧"},
]

SERVICES = [
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
    {"name": "PlayStation Network", "url": "https://auth.api.sonyentertainmentnetwork.com", "icon": "🔷"},
]

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ----------------------------------------------------
# 1. SONDAS DE REDE
# ----------------------------------------------------
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


def fetch_ssh_metrics(ip, username, password, port=22):
    if not ip or not username or not password:
        return {"error": "Credenciais SSH não configuradas (ONT_IP / ONT_USER / ONT_PASS no .env)."}

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
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
    except paramiko.AuthenticationException:
        return {"error": "Usuário ou senha incorretos no SSH."}
    except Exception as e:  # noqa: BLE001 — qualquer falha vira mensagem na tela
        return {"error": f"Falha na conexão SSH com {ip}: {e}"}
    finally:
        ssh.close()


# ----------------------------------------------------
# 2. COLETOR EM SEGUNDO PLANO
# ----------------------------------------------------
class Collector:
    """Roda as sondas em threads próprias e guarda o histórico em memória."""

    def __init__(self):
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ssh_wake = threading.Event()
        self._pool = ThreadPoolExecutor(max_workers=len(DNS_TARGETS) + len(SERVICES))

        self.ping_latest = {}            # nome -> (latência, perda)
        self.http_latest = {}            # nome -> (ms, ok, detalhe)
        self.ping_history = deque(maxlen=HISTORY_POINTS)   # (datetime, {nome: (lat, perda)})
        self.http_history = deque(maxlen=HISTORY_POINTS)   # (datetime, {nome: (ms, ok)})
        self.last_probe = None

        self.ssh_creds = (os.getenv("ONT_IP", ""), os.getenv("ONT_USER", ""), os.getenv("ONT_PASS", ""))
        self.ssh_latest = None
        self.ssh_last_time = None
        self.ssh_history = deque(maxlen=SSH_HISTORY_POINTS)  # (datetime, cpu, ram)

        threading.Thread(target=self._probe_loop, name="netmon-probe", daemon=True).start()
        threading.Thread(target=self._ssh_loop, name="netmon-ssh", daemon=True).start()

    def stop(self):
        self._stop.set()
        self._ssh_wake.set()
        self._pool.shutdown(wait=False, cancel_futures=True)

    # --- ping + HTTP -------------------------------------------------
    def _probe_once(self):
        ping_futs = {t["name"]: self._pool.submit(ping_host, t["ip"]) for t in DNS_TARGETS}
        http_futs = {s["name"]: self._pool.submit(check_service, s["url"]) for s in SERVICES}
        pings = {name: f.result() for name, f in ping_futs.items()}
        https = {name: f.result() for name, f in http_futs.items()}
        now = dt.datetime.now()
        with self._lock:
            self.ping_latest = pings
            self.http_latest = https
            self.ping_history.append((now, pings))
            self.http_history.append((now, {n: (ms, ok) for n, (ms, ok, _d) in https.items()}))
            self.last_probe = now

    def _probe_loop(self):
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                self._probe_once()
            except RuntimeError:  # pool encerrado durante o stop()
                return
            # Mantém o ritmo de 5s; se a rodada atrasar, a próxima começa logo em seguida
            self._stop.wait(max(0.0, PROBE_INTERVAL_S - (time.monotonic() - started)))

    # --- SSH ---------------------------------------------------------
    def set_ssh_credentials(self, ip, user, password):
        with self._lock:
            self.ssh_creds = (ip, user, password)
        self._ssh_wake.set()

    def _ssh_loop(self):
        while not self._stop.is_set():
            with self._lock:
                creds = self.ssh_creds
            data = fetch_ssh_metrics(*creds)
            now = dt.datetime.now()
            with self._lock:
                self.ssh_latest = data
                self.ssh_last_time = now
                if not data.get("error") and data["CPU_Pct"] is not None and data["Memoria_Pct"] is not None:
                    self.ssh_history.append((now, data["CPU_Pct"], data["Memoria_Pct"]))
            self._ssh_wake.wait(SSH_INTERVAL_S)
            self._ssh_wake.clear()

    # --- leitura para a interface ------------------------------------
    def snapshot(self):
        with self._lock:
            return {
                "ping_latest": dict(self.ping_latest),
                "http_latest": dict(self.http_latest),
                "ping_history": list(self.ping_history),
                "http_history": list(self.http_history),
                "last_probe": self.last_probe,
                "ssh_creds": self.ssh_creds,
                "ssh_latest": self.ssh_latest,
                "ssh_last_time": self.ssh_last_time,
                "ssh_history": list(self.ssh_history),
            }


@st.cache_resource(on_release=lambda c: c.stop())
def get_collector():
    return Collector()


# ----------------------------------------------------
# 3. INTERFACE
# ----------------------------------------------------
st.set_page_config(page_title="Monitor de Rede - Windows", layout="wide", page_icon="🌐")

st.markdown("""
    <style>
    .card-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(165px, 1fr));
        gap: 10px;
        margin-bottom: 12px;
    }
    .metric-card {
        background-color: #1e1e2e;
        border-radius: 10px;
        padding: 12px 16px;
        border-left: 5px solid #6c757d;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        min-width: 0;
    }
    .chart-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 4px 14px;
        font-size: 0.78rem;
        color: #cdd6f4;
        margin: -6px 0 18px 0;
    }
    .lg-item { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
    .lg-swatch { width: 14px; height: 4px; border-radius: 2px; flex: none; }
    @media (max-width: 640px) {
        .card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
        .metric-card { padding: 9px 11px; border-left-width: 4px; }
        .card-value { font-size: 1.15rem !important; }
        .card-title { font-size: 0.78rem !important; }
        h1 { font-size: 1.55rem !important; }
        h3 { font-size: 1.1rem !important; }
        .block-container { padding-left: 0.8rem !important; padding-right: 0.8rem !important; }
    }
    .metric-card-green { border-left-color: #28a745 !important; }
    .metric-card-orange { border-left-color: #fd7e14 !important; }
    .metric-card-red { border-left-color: #dc3545 !important; }
    .card-title { font-size: 0.85rem; color: #a6adc8; font-weight: 600; margin-bottom: 4px; }
    .card-value { font-size: 1.4rem; font-weight: bold; color: #cdd6f4; }
    .card-title, .card-value { overflow-wrap: anywhere; }
    .card-badge { font-size: 0.72rem; font-weight: 600; padding: 2px 8px; border-radius: 12px; display: inline-block; margin-top: 4px; }
    .badge-green { background-color: rgba(40, 167, 69, 0.2); color: #28a745; }
    .badge-orange { background-color: rgba(253, 126, 20, 0.2); color: #fd7e14; }
    .badge-red { background-color: rgba(220, 53, 69, 0.2); color: #dc3545; }
    </style>
""", unsafe_allow_html=True)

LEVEL_STYLE = {
    "green": ("metric-card-green", "badge-green", "🟢"),
    "orange": ("metric-card-orange", "badge-orange", "🟠"),
    "red": ("metric-card-red", "badge-red", "🔴"),
}


def card(icon, title, value, badge, level):
    card_cls, badge_cls, dot = LEVEL_STYLE[level]
    return (
        f'<div class="metric-card {card_cls}">'
        f'<div class="card-title">{icon} {html.escape(title)}</div>'
        f'<div class="card-value">{html.escape(value)}</div>'
        f'<div class="card-badge {badge_cls}">{dot} {html.escape(badge)}</div>'
        f"</div>"
    )


def render_grid(cards):
    # Grade CSS: 5+ colunas no PC, 2 no celular, sempre na ordem da lista
    st.markdown(f'<div class="card-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


# Paleta de 20 cores distintas e legíveis em fundo escuro (uma por série)
PALETTE = [
    "#4e9bf5", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#c49c7a", "#bab0ac",
    "#8cd17d", "#86d3f0", "#ffbe7d", "#a0a8ff", "#f1ce63",
    "#d37295", "#fabfd2", "#d4b84a", "#4fc1b0", "#e6a6ff",
]


def color_map(names):
    return {n: PALETTE[i % len(PALETTE)] for i, n in enumerate(names)}


def legend_html(names, colors):
    items = "".join(
        f'<span class="lg-item"><span class="lg-swatch" style="background:{colors[n]}"></span>'
        f"{html.escape(n)}</span>"
        for n in names
    )
    return f'<div class="chart-legend">{items}</div>'


def history_chart(history, names, pick, y_title, y_max=None):
    """Gráfico de linhas com eixo Y travado em 0 e zoom só no eixo do tempo.

    history: [(datetime, {nome: valores})]; pick extrai o número de `valores`.
    """
    rows = [
        {"Horário": ts, "Alvo": n, "Valor": pick(vals[n])}
        for ts, vals in history for n in names if n in vals
    ]
    df = pd.DataFrame(rows, columns=["Horário", "Alvo", "Valor"])
    colors = color_map(names)

    # Zoom (roda do mouse) e arraste só no eixo X; duplo clique volta ao normal.
    # O arraste usa eventos de mouse para não "prender" a rolagem da página no celular.
    zoom = alt.selection_interval(
        bind="scales", encodings=["x"], zoom="wheel!",
        translate="[mousedown, window:mouseup] > window:mousemove!",
    )
    y_scale = (alt.Scale(domain=[0, y_max], clamp=True) if y_max is not None
               else alt.Scale(domainMin=0, nice=True, clamp=True))

    base = alt.Chart(df).encode(
        x=alt.X("Horário:T", title=None,
                axis=alt.Axis(labelExpr="timeFormat(datum.value, '%H:%M:%S')",
                              labelOverlap=True, tickCount=5, grid=False)),
        y=alt.Y("Valor:Q", title=y_title, scale=y_scale, axis=alt.Axis(tickCount=5)),
        color=alt.Color("Alvo:N", legend=None,
                        scale=alt.Scale(domain=list(names), range=[colors[n] for n in names])),
    )
    lines = base.mark_line(strokeWidth=1.8, clip=True).add_params(zoom)
    # Pontos invisíveis só para o tooltip ao passar o mouse / tocar
    points = base.mark_point(size=70, opacity=0, clip=True).encode(
        tooltip=[
            alt.Tooltip("Alvo:N", title="Alvo"),
            alt.Tooltip("Horário:T", title="Horário", format="%H:%M:%S"),
            alt.Tooltip("Valor:Q", title=y_title, format=".1f"),
        ]
    )
    st.altair_chart(alt.layer(lines, points).properties(height=280), width="stretch")
    st.markdown(legend_html(names, colors), unsafe_allow_html=True)


def waiting_message(snap):
    if snap["last_probe"] is None:
        st.info("⏳ Coletando a primeira amostra…")
        return True
    return False


st.title("🌐 Monitor de Rede & Latência")
collector = get_collector()

# Pausar congela a tela (a coleta continua em segundo plano). Útil para dar zoom
# nos gráficos sem que a atualização a cada 5s volte o zoom ao normal.
paused = st.toggle("⏸️ Pausar tela (para dar zoom nos gráficos)", key="paused")
if not paused or "frozen_snapshot" not in st.session_state:
    st.session_state.frozen_snapshot = collector.snapshot()


def current_snapshot():
    if st.session_state.get("paused"):
        return st.session_state.frozen_snapshot
    return collector.snapshot()

tab1, tab2, tab3 = st.tabs([
    "⚡ Latência & DNS",
    "🌐 Serviços Web",
    "📡 ONT (SSH)",
])


@st.fragment(run_every=PROBE_INTERVAL_S)
def render_ping_tab():
    snap = current_snapshot()
    st.caption(f"Última coleta: {snap['last_probe']:%H:%M:%S}" if snap["last_probe"] else "")
    if waiting_message(snap):
        return

    cards = []
    for t in DNS_TARGETS:
        lat, loss = snap["ping_latest"].get(t["name"], (None, 100))
        level = "green" if loss == 0 else ("orange" if loss < 100 else "red")
        if lat is None:
            value = "Offline"
        else:
            value = "<1 ms" if lat < 1 else f"{lat:.0f} ms"
        cards.append(card(t["icon"], t["name"], value, f"{loss}% Perda", level))
    render_grid(cards)

    names = [t["name"] for t in DNS_TARGETS]
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("📊 Latência (ms) · 30 min")
        history_chart(snap["ping_history"], names, lambda v: v[0], "Latência (ms)")
    with g2:
        st.subheader("📉 Perda de Pacotes (%) · 30 min")
        history_chart(snap["ping_history"], names, lambda v: v[1], "Perda (%)", y_max=100)


@st.fragment(run_every=PROBE_INTERVAL_S)
def render_services_tab():
    snap = current_snapshot()
    st.caption(f"Última coleta: {snap['last_probe']:%H:%M:%S}" if snap["last_probe"] else "")
    if waiting_message(snap):
        return

    history = snap["http_history"]
    cards = []
    availability = {}
    for s in SERVICES:
        name = s["name"]
        samples = [row[name][1] for _, row in history if name in row]
        avail = 100 * sum(samples) / len(samples) if samples else 0.0
        availability[name] = round(avail, 1)

        ms, ok, detail = snap["http_latest"].get(name, (None, False, "Sem dados"))
        if ok:
            level = "green" if avail >= 99.5 else "orange"
            value = f"{ms:.0f} ms"
        else:
            level, value = "red", "Falha"
        cards.append(card(s["icon"], name, value, f"{avail:.1f}% disp. · {detail}", level))
    render_grid(cards)

    names = [s["name"] for s in SERVICES]
    colors = color_map(names)
    avail_df = pd.DataFrame({"Serviço": names, "Disponibilidade": [availability[n] for n in names]})

    g1, g2 = st.columns(2)
    with g1:
        st.subheader("📊 Tempo de Resposta (ms) · 30 min")
        history_chart(history, names, lambda v: v[0], "Resposta (ms)")
    with g2:
        st.subheader("✅ Disponibilidade (%) · 30 min")
        bars = alt.Chart(avail_df).mark_bar(cornerRadiusEnd=3).encode(
            x=alt.X("Disponibilidade:Q", title=None, scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("Serviço:N", title=None, sort=names,
                    axis=alt.Axis(labelLimit=0, labelOverlap=False, labelFontSize=11)),
            color=alt.Color("Serviço:N", legend=None,
                            scale=alt.Scale(domain=names, range=[colors[n] for n in names])),
            tooltip=[alt.Tooltip("Serviço:N"), alt.Tooltip("Disponibilidade:Q", format=".1f")],
        ).properties(height=24 * len(names))
        st.altair_chart(bars, width="stretch")


@st.fragment(run_every=PROBE_INTERVAL_S)
def render_ssh_status():
    snap = current_snapshot()
    data = snap["ssh_latest"]
    if data is None:
        st.info("⏳ Conectando na ONT via SSH…")
        return
    if data.get("error"):
        st.error(f"🔴 {data['error']}")
        return

    st.success(f"🟢 Conectado e atualizado via SSH às {snap['ssh_last_time']:%H:%M:%S}")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("⏱️ Uptime (Tempo Online)", data["Uptime"])
    with c2:
        mem = data["Memoria_Pct"]
        st.metric("🧠 Uso de Memória RAM", f"{mem}%" if mem is not None else "N/A")
        if mem is not None:
            st.progress(mem / 100.0)
    with c3:
        cpu = data["CPU_Pct"]
        st.metric("⚡ Uso do Processador (CPU)", f"{cpu}%" if cpu is not None else "N/A")
        if cpu is not None:
            st.progress(cpu / 100.0)

    if snap["ssh_history"]:
        st.subheader("📊 Consumo de Hardware da ONT (últimas 30 coletas)")
        hist = [(ts, {"CPU (%)": cpu, "RAM (%)": ram}) for ts, cpu, ram in snap["ssh_history"]]
        history_chart(hist, ["CPU (%)", "RAM (%)"], lambda v: v, "Uso (%)", y_max=100)


with tab1:
    st.subheader(f"⚡ Latência dos DNS públicos ({PROBE_INTERVAL_S}s)")
    render_ping_tab()

with tab2:
    st.subheader(f"🌐 Web, Redes, Streaming & Games ({PROBE_INTERVAL_S}s)")
    render_services_tab()

with tab3:
    st.subheader(f"📡 Roteador MitraStar (coleta a cada {SSH_INTERVAL_S}s)")
    cur_ip, cur_user, _cur_pass = collector.snapshot()["ssh_creds"]
    with st.expander("⚙️ Credenciais SSH"):
        with st.form("ssh_form"):
            f1, f2, f3 = st.columns(3)
            new_ip = f1.text_input("IP da ONT", cur_ip)
            new_user = f2.text_input("Usuário SSH", cur_user)
            # A senha nunca é enviada ao navegador; em branco = mantém a atual (.env)
            new_pass = f3.text_input("Senha SSH", "", type="password",
                                     placeholder="(manter a senha atual)")
            if st.form_submit_button("Aplicar e reconectar"):
                collector.set_ssh_credentials(new_ip.strip(), new_user.strip(),
                                              new_pass or collector.snapshot()["ssh_creds"][2])
                st.toast("Reconectando com as novas credenciais…")
    render_ssh_status()
