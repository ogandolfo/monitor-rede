"""Monitor de Rede & Latência — dashboard Streamlit (Windows).

A coleta roda em segundo plano (pacote `netmon`), grava o histórico em
data/netmon.db e detecta quedas. Esta página apenas lê e desenha.
"""
import datetime as dt
import html
import time

import altair as alt
import pandas as pd
import streamlit as st

from netmon import config as cfg
from netmon import credentials
from netmon.collector import AlreadyRunning, get_global_collector
from netmon.incidents import KIND_ICONS, KIND_MONITOR_OFF, OUTAGE_KINDS

st.set_page_config(page_title="Monitor de Rede - Windows", layout="wide", page_icon="🌐")

# ----------------------------------------------------
# ESTILO
# ----------------------------------------------------
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
    </style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# SENHA DO PAINEL (só para acessos vindos de outros aparelhos)
# ----------------------------------------------------
# st.context.ip_address é None quando o acesso vem deste próprio PC (localhost).
if (st.context.ip_address is not None
        and credentials.panel_password_enabled()
        and not st.session_state.get("auth_ok")):
    st.title("🔒 Monitor de Rede")
    with st.form("login"):
        pwd = st.text_input("Senha do painel", type="password")
        if st.form_submit_button("Entrar"):
            if credentials.check_panel_password(pwd):
                st.session_state.auth_ok = True
                st.rerun()
            time.sleep(1.5)   # atrasa tentativas por força bruta
            st.error("Senha incorreta.")
    st.stop()


# ----------------------------------------------------
# COLETOR
# ----------------------------------------------------
# Normalmente o coletor já foi iniciado pelo run.py antes do painel subir;
# se o monitor foi aberto com "streamlit run monitor.py", ele nasce aqui.
try:
    collector = get_global_collector()
except AlreadyRunning:
    st.error(
        "⚠️ O monitor já está rodando em outra janela ou na inicialização do Windows. "
        "Abra **http://localhost:8501** para vê-lo."
    )
    st.stop()

# ----------------------------------------------------
# COMPONENTES
# ----------------------------------------------------
LEVEL_STYLE = {
    "green": ("metric-card-green", "badge-green", "🟢"),
    "orange": ("metric-card-orange", "badge-orange", "🟠"),
    "red": ("metric-card-red", "badge-red", "🔴"),
}

# Paleta de 20 cores distintas e legíveis em fundo escuro (uma por série)
PALETTE = [
    "#4e9bf5", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#c49c7a", "#bab0ac",
    "#8cd17d", "#86d3f0", "#ffbe7d", "#a0a8ff", "#f1ce63",
    "#d37295", "#fabfd2", "#d4b84a", "#4fc1b0", "#e6a6ff",
]

WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

# Escalas FIXAS do mapa de calor (verde = ótimo, vermelho = ruim) — não dependem
# dos dados do período. Os pontos ficam em netmon/config.py.
HEAT_COLORS = ["#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027"]


def _heat_caption(stops, unit, labels=("ótimo", "aceitável", "ruim", "péssimo")):
    def fmt(v):
        return f"{v:g}".replace(".", ",") + unit
    s = stops
    return (f"🟢 até {fmt(s[1])} {labels[0]} · 🟡 ~{fmt(s[2])} {labels[1]} · "
            f"🟠 ~{fmt(s[3])} {labels[2]} · 🔴 {fmt(s[4])} ou mais {labels[3]}")


HEAT_SCALES = {
    "Latência (ms)": {"stops": cfg.HEAT_LATENCY_STOPS_MS,
                      "caption": _heat_caption(cfg.HEAT_LATENCY_STOPS_MS, " ms")},
    "Perda (%)": {"stops": cfg.HEAT_LOSS_STOPS_PCT,
                  "caption": _heat_caption(cfg.HEAT_LOSS_STOPS_PCT, "%")},
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


def color_map(names):
    return {n: PALETTE[i % len(PALETTE)] for i, n in enumerate(names)}


def legend_html(names, colors):
    items = "".join(
        f'<span class="lg-item"><span class="lg-swatch" style="background:{colors[n]}"></span>'
        f"{html.escape(n)}</span>"
        for n in names
    )
    return f'<div class="chart-legend">{items}</div>'


def lines_chart(df, names, y_title, y_max=None, time_fmt="%H:%M:%S", height=280):
    """Linhas com eixo Y travado em 0 e zoom só no eixo do tempo.

    df em formato longo: colunas Horário (datetime), Alvo, Valor.
    """
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
                axis=alt.Axis(labelExpr=f"timeFormat(datum.value, '{time_fmt}')",
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
            alt.Tooltip("Horário:T", title="Horário", format="%d/%m %H:%M:%S"),
            alt.Tooltip("Valor:Q", title=y_title, format=".1f"),
        ]
    )
    st.altair_chart(alt.layer(lines, points).properties(height=height), width="stretch")
    st.markdown(legend_html(names, colors), unsafe_allow_html=True)


def history_chart(history, names, pick, y_title, y_max=None):
    """history: [(datetime, {nome: valores})]; pick extrai o número de `valores`."""
    rows = [
        {"Horário": ts, "Alvo": n, "Valor": pick(vals[n])}
        for ts, vals in history for n in names if n in vals
    ]
    lines_chart(pd.DataFrame(rows, columns=["Horário", "Alvo", "Valor"]), names, y_title, y_max)


def fmt_duration(seconds):
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}min"
    if m:
        return f"{m}min {s:02d}s"
    return f"{s}s"


def waiting(last):
    if last is None:
        st.info("⏳ Coletando a primeira amostra…")
        return True
    return False


# ----------------------------------------------------
# CABEÇALHO
# ----------------------------------------------------
st.title("🌐 Monitor de Rede & Latência")

# Pausar congela a tela (a coleta continua em segundo plano). Útil para dar zoom
# nos gráficos sem que a atualização a cada 5s volte o zoom ao normal.
paused = st.toggle("⏸️ Pausar tela (para dar zoom nos gráficos)", key="paused")
if not paused or "frozen_snapshot" not in st.session_state:
    st.session_state.frozen_snapshot = collector.snapshot()


def current_snapshot():
    if st.session_state.get("paused"):
        return st.session_state.frozen_snapshot
    return collector.snapshot()


@st.fragment(run_every=cfg.PING_INTERVAL_S)
def render_active_incidents():
    active = collector.snapshot()["active_incidents"]
    now = time.time()
    for kind, target, start, detail in sorted(active, key=lambda a: a[2] or now):
        dur = fmt_duration(now - start) if start else ""
        who = "" if target in ("Gateway", "DNS públicos") else f" — {target}"
        st.error(f"{KIND_ICONS.get(kind, '⚠️')} **{kind}{who}** há {dur} · {detail}")


render_active_incidents()

tab1, tab2, tab3, tab4 = st.tabs([
    "⚡ Latência & DNS",
    "🌐 Serviços Web",
    "📈 Histórico",
    "📡 ONT (SSH)",
])


# ----------------------------------------------------
# ABA 1: PING
# ----------------------------------------------------
@st.fragment(run_every=cfg.PING_INTERVAL_S)
def render_ping_tab():
    snap = current_snapshot()
    if waiting(snap["last_ping"]):
        return
    st.caption(f"Última coleta: {snap['last_ping']:%H:%M:%S}")

    cards = []
    for t in cfg.PING_TARGETS:
        lat, loss = snap["ping_latest"].get(t["name"], (None, 100))
        level = "green" if loss == 0 else ("orange" if loss < 100 else "red")
        if lat is None:
            value = "Offline"
        else:
            value = "<1 ms" if lat < 1 else f"{lat:.0f} ms"
        cards.append(card(t["icon"], t["name"], value, f"{loss}% Perda", level))
    render_grid(cards)

    names = [t["name"] for t in cfg.PING_TARGETS]
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("📊 Latência (ms) · 30 min")
        history_chart(snap["ping_history"], names, lambda v: v[0], "Latência (ms)")
    with g2:
        st.subheader("📉 Perda de Pacotes (%) · 30 min")
        history_chart(snap["ping_history"], names, lambda v: v[1], "Perda (%)", y_max=100)


# ----------------------------------------------------
# ABA 2: SERVIÇOS HTTP
# ----------------------------------------------------
@st.fragment(run_every=cfg.PING_INTERVAL_S)
def render_services_tab():
    snap = current_snapshot()
    if waiting(snap["last_http"]):
        return
    st.caption(f"Última checagem: {snap['last_http']:%H:%M:%S} · os sites são verificados a cada "
               f"{cfg.HTTP_INTERVAL_S}s para não sobrecarregar os servidores")

    history = snap["http_history"]
    cards = []
    availability = {}
    for s in cfg.SERVICES:
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

    names = [s["name"] for s in cfg.SERVICES]
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


# ----------------------------------------------------
# ABA 3: HISTÓRICO (SQLite)
# ----------------------------------------------------
PERIODS = {
    "Últimas 24 horas": (1, "5min", "%H:%M"),
    "Últimos 7 dias": (7, "30min", "%d/%m %Hh"),
    "Últimos 30 dias": (30, "2h", "%d/%m"),
    "Últimos 90 dias": (90, "6h", "%d/%m"),
}


def to_local(ts_series):
    return pd.to_datetime(ts_series.map(dt.datetime.fromtimestamp))


def render_history_tab():
    storage = collector.storage
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    period = c1.selectbox("Período", list(PERIODS), index=0, key="hist_period")
    c2.button("🔄 Atualizar", width="stretch")
    days, bucket, time_fmt = PERIODS[period]
    now = int(time.time())
    since = now - days * 86400

    first = storage.first_ts()
    if first is None:
        st.info("O histórico começa a ser gravado agora; volte em alguns minutos.")
        return
    st.caption(f"Histórico gravado desde {dt.datetime.fromtimestamp(first):%d/%m/%Y %H:%M} "
               f"· guardado por {cfg.RETENTION_DAYS} dias em data/netmon.db")

    # --- Incidentes do período ------------------------------------------
    inc = storage.incidents(since)
    if not inc.empty:
        inc["end_eff"] = inc["end_ts"].fillna(now).astype(int)
        inc["dur"] = (inc["end_eff"].clip(upper=now) - inc["start_ts"].clip(lower=since)).clip(lower=0)
    outages = inc[inc["kind"].isin(OUTAGE_KINDS)] if not inc.empty else inc
    downtime = int(outages["dur"].sum()) if not outages.empty else 0

    # --- Ping por minuto -> séries agregadas ----------------------------
    pm = storage.ping_minutes(since)
    dns_names = [t["name"] for t in cfg.DNS_TARGETS]
    internet = (pm[pm["target"].isin(dns_names)]
                .groupby("ts").agg(lat=("lat_avg", "mean"), loss=("loss_avg", "mean"))
                .reset_index())
    gateway = (pm[pm["target"] == cfg.GATEWAY_NAME][["ts", "lat_avg", "loss_avg"]]
               .rename(columns={"lat_avg": "lat", "loss_avg": "loss"}))

    # Tempo coberto pelo monitor no período = desde o início dos dados, menos períodos desligado
    window_start = max(since, first)
    off = inc[inc["kind"] == KIND_MONITOR_OFF] if not inc.empty else inc
    off_time = int(off["dur"].clip(lower=0).sum()) if not off.empty else 0
    monitored = max(0, now - window_start - off_time)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("⏱️ Tempo sem internet", fmt_duration(downtime))
    m2.metric("🔌 Quedas", len(outages))
    m3.metric("📶 Latência média (internet)",
              f"{internet['lat'].mean():.0f} ms" if internet["lat"].notna().any() else "—")
    m4.metric("✅ Disponibilidade",
              f"{max(0.0, 100 * (1 - downtime / monitored)):.2f}%" if monitored else "—",
              help="Sobre o tempo em que o monitor estava ligado.")

    if not internet.empty:
        series = []
        for label, df in (("Internet (média dos DNS)", internet), ("Gateway (rede local)", gateway)):
            if df.empty:
                continue
            d = df.copy()
            d["Horário"] = to_local(d["ts"])
            d = d.set_index("Horário")[["lat", "loss"]].resample(bucket).mean().reset_index()
            d["Alvo"] = label
            series.append(d)
        agg = pd.concat(series, ignore_index=True)
        names = list(agg["Alvo"].unique())

        g1, g2 = st.columns(2)
        with g1:
            st.subheader("📊 Latência (ms)")
            lines_chart(agg.rename(columns={"lat": "Valor"})[["Horário", "Alvo", "Valor"]],
                        names, "Latência (ms)", time_fmt=time_fmt)
        with g2:
            st.subheader("📉 Perda de Pacotes (%)")
            lines_chart(agg.rename(columns={"loss": "Valor"})[["Horário", "Alvo", "Valor"]],
                        names, "Perda (%)", y_max=100, time_fmt=time_fmt)

        # --- Mapa de calor: dia da semana x hora ------------------------
        st.subheader("🗓️ Em que horário a internet piora?")
        metric = st.radio("Métrica", ["Latência (ms)", "Perda (%)"], horizontal=True,
                          key="heat_metric", label_visibility="collapsed")
        col = "lat" if metric.startswith("Lat") else "loss"
        h = internet.copy()
        h["Horário"] = to_local(h["ts"])
        h["Dia"] = h["Horário"].dt.dayofweek.map(lambda i: WEEKDAYS[i])
        h["Hora"] = h["Horário"].dt.hour
        heat = h.groupby(["Dia", "Hora"])[col].mean().reset_index().rename(columns={col: "Valor"})
        heatmap = alt.Chart(heat).mark_rect(cornerRadius=2).encode(
            x=alt.X("Hora:O", title="Hora do dia", scale=alt.Scale(domain=list(range(24))),
                    axis=alt.Axis(labelAngle=0, labelOverlap=True)),
            y=alt.Y("Dia:O", title=None, scale=alt.Scale(domain=WEEKDAYS),
                    axis=alt.Axis(labelOverlap=False)),
            color=alt.Color("Valor:Q", title=metric,
                            scale=alt.Scale(domain=HEAT_SCALES[metric]["stops"], range=HEAT_COLORS,
                                            clamp=True),
                            legend=alt.Legend(orient="bottom", gradientLength=240,
                                              values=HEAT_SCALES[metric]["stops"])),
            tooltip=[alt.Tooltip("Dia:O"), alt.Tooltip("Hora:O"),
                     alt.Tooltip("Valor:Q", title=metric, format=".1f")],
        ).properties(height=alt.Step(26))
        st.altair_chart(heatmap, width="stretch")
        st.caption(f"Cada quadrado é a média daquele dia da semana e hora no período escolhido. "
                   f"{HEAT_SCALES[metric]['caption']}")

    # --- Tabela de incidentes -------------------------------------------
    st.subheader("🚨 Registro de quedas e instabilidades")
    if inc.empty:
        st.success("Nenhum incidente registrado no período. 🎉")
        return
    kinds = sorted(inc["kind"].unique())
    default = [k for k in kinds if k != KIND_MONITOR_OFF]
    chosen = st.multiselect("Tipos", kinds, default=default, key="inc_kinds")
    view = inc[inc["kind"].isin(chosen)].copy()
    table = pd.DataFrame({
        "Início": to_local(view["start_ts"]),
        "Fim": pd.to_datetime([dt.datetime.fromtimestamp(e) if pd.notna(e) else None
                               for e in view["end_ts"]]),
        "Duração": [fmt_duration(d) + (" ⏳ em andamento" if pd.isna(e) else "")
                    for d, e in zip(view["dur"], view["end_ts"])],
        "Causa provável": view["kind"].map(lambda k: f"{KIND_ICONS.get(k, '')} {k}"),
        "Alvo": view["target"],
        "Detalhe": view["detail"],
    })
    st.dataframe(
        table, hide_index=True, width="stretch",
        column_config={
            "Início": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm:ss"),
            "Fim": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm:ss"),
        },
    )
    st.download_button(
        "⬇️ Baixar registro (CSV)",
        table.assign(Início=table["Início"].dt.strftime("%d/%m/%Y %H:%M:%S"),
                     Fim=[f"{f:%d/%m/%Y %H:%M:%S}" if pd.notna(f) else "em andamento"
                          for f in table["Fim"]])
             .to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name=f"quedas_internet_{dt.date.today():%Y-%m-%d}.csv",
        mime="text/csv",
        help="Útil como prova ao reclamar com a operadora ou na Anatel.",
    )
    with st.expander("ℹ️ Como a causa é decidida"):
        st.markdown(
            f"""
- **🏠 Rede local** — o roteador (gateway) parou de responder: problema no Wi-Fi, cabo ou roteador.
- **🌐 Internet / Operadora** — o roteador responde, mas {cfg.ISP_DOWN_MIN_TARGETS}+ dos {len(cfg.DNS_TARGETS)} DNS públicos não.
- **〰️ Instabilidade** — internet no ar, mas com perda média ≥ {cfg.INSTABILITY_LOSS_PCT}% ou latência mediana ≥ {cfg.INSTABILITY_LATENCY_MS} ms.
- **🧩 Serviço fora do ar** — internet ok, mas o site falhou por {cfg.SERVICE_OPEN_AFTER} checagens seguidas.
- **💤 Monitor desligado** — período sem dados (PC desligado ou monitor fechado).

Um incidente só é aberto após {cfg.OUTAGE_OPEN_AFTER * cfg.PING_INTERVAL_S}s seguidos de falha, para ignorar soluços isolados.
"""
        )


# ----------------------------------------------------
# ABA 4: ONT VIA SSH
# ----------------------------------------------------
@st.fragment(run_every=cfg.PING_INTERVAL_S)
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


PASS_SOURCE_TEXT = {
    "keyring": "🔐 Senha guardada no Gerenciador de Credenciais do Windows.",
    "env": "⚠️ Senha lida do arquivo .env (texto puro). Salve-a abaixo para movê-la ao Gerenciador de Credenciais.",
    "memória": "⚠️ Não foi possível salvar no Gerenciador de Credenciais; a senha vale só até fechar o monitor.",
    None: "⚠️ Nenhuma senha configurada.",
}

with tab1:
    st.subheader(f"⚡ Latência dos DNS públicos ({cfg.PING_INTERVAL_S}s)")
    render_ping_tab()

with tab2:
    st.subheader(f"🌐 Web, Redes, Streaming & Games ({cfg.HTTP_INTERVAL_S}s)")
    render_services_tab()

with tab3:
    st.subheader("📈 Histórico e registro de quedas")
    render_history_tab()

with tab4:
    st.subheader(f"📡 Roteador MitraStar (coleta a cada {cfg.SSH_INTERVAL_S}s)")
    snap0 = collector.snapshot()
    st.caption(PASS_SOURCE_TEXT.get(snap0["ssh_pass_source"], ""))
    with st.expander("⚙️ Credenciais SSH"):
        with st.form("ssh_form"):
            f1, f2, f3 = st.columns(3)
            new_ip = f1.text_input("IP da ONT", snap0["ssh_ip"])
            new_user = f2.text_input("Usuário SSH", snap0["ssh_user"])
            # A senha nunca é enviada ao navegador; em branco = mantém a atual
            new_pass = f3.text_input("Senha SSH", "", type="password",
                                     placeholder="(manter a senha atual)")
            if st.form_submit_button("Salvar e reconectar"):
                collector.set_ssh_credentials(new_ip.strip(), new_user.strip(), new_pass or None)
                st.toast("Reconectando com as novas credenciais…")
    render_ssh_status()
