"""Configurações e listas de alvos do monitor."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"                     # fica fora do Git (.gitignore)
DB_PATH = DATA_DIR / "netmon.db"
KNOWN_HOSTS_PATH = DATA_DIR / "ont_known_hosts"
LOCK_PATH = DATA_DIR / "netmon.lock"

# --- Intervalos --------------------------------------------------------
PING_INTERVAL_S = 5           # ping nos DNS e no gateway
HTTP_INTERVAL_S = 60          # checagem dos sites (gentil com os servidores)
SSH_INTERVAL_S = 120          # métricas da ONT

LIVE_WINDOW_S = 30 * 60       # janela dos gráficos "ao vivo" (30 min)
PING_LIVE_POINTS = LIVE_WINDOW_S // PING_INTERVAL_S
HTTP_LIVE_POINTS = LIVE_WINDOW_S // HTTP_INTERVAL_S
SSH_LIVE_POINTS = 30

RETENTION_DAYS = 180          # histórico guardado em disco

# --- Detecção de incidentes -------------------------------------------
# Quantas rodadas seguidas ruins abrem um incidente / boas o encerram
OUTAGE_OPEN_AFTER = 2         # 2 x 5s = 10s sem resposta
OUTAGE_CLOSE_AFTER = 2
INSTABILITY_OPEN_AFTER = 3    # 15s de instabilidade
INSTABILITY_CLOSE_AFTER = 3
SERVICE_OPEN_AFTER = 2        # 2 x 60s = 2 min fora do ar
SERVICE_CLOSE_AFTER = 1
ISP_DOWN_MIN_TARGETS = 7      # nº de DNS sem resposta para considerar "internet caiu"
# Limites de instabilidade (mesma régua do mapa de calor: 10% / 100 ms = "péssimo").
# Precisam durar INSTABILITY_OPEN_AFTER rodadas seguidas para virar incidente.
INSTABILITY_LOSS_PCT = 10     # perda média nos DNS que caracteriza instabilidade
INSTABILITY_LATENCY_MS = 100  # latência mediana nos DNS que caracteriza instabilidade
MONITOR_GAP_S = 120           # lacuna mínima para registrar "monitor desligado"

# --- Alvos -------------------------------------------------------------
GATEWAY_NAME = "Gateway"
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
]
PING_TARGETS = DNS_TARGETS + [{"name": GATEWAY_NAME, "ip": GATEWAY_IP, "icon": "🖧"}]

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
