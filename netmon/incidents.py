"""Detecção de quedas e instabilidades com diagnóstico da causa provável.

Lógica do diagnóstico (avaliada a cada rodada de ping):
  * Gateway sem resposta                       -> problema na REDE LOCAL (Wi-Fi, cabo, roteador)
  * Gateway ok, mas quase todos os DNS mudos   -> problema na INTERNET / OPERADORA
  * Gateway ok, DNS com perda/latência alta    -> INSTABILIDADE na internet
  * Internet ok, mas um site não responde      -> problema só naquele SERVIÇO
"""
import statistics

from . import config as cfg

KIND_LOCAL = "Rede local"
KIND_ISP = "Internet / Operadora"
KIND_UNSTABLE = "Instabilidade"
KIND_SERVICE = "Serviço fora do ar"
KIND_MONITOR_OFF = "Monitor desligado"

KIND_ICONS = {
    KIND_LOCAL: "🏠",
    KIND_ISP: "🌐",
    KIND_UNSTABLE: "〰️",
    KIND_SERVICE: "🧩",
    KIND_MONITOR_OFF: "💤",
}

# Tipos que contam como "fiquei sem internet"
OUTAGE_KINDS = (KIND_LOCAL, KIND_ISP)


class _Track:
    __slots__ = ("bad", "good", "first_bad", "first_good", "incident_id", "start", "detail")

    def __init__(self):
        self.bad = self.good = 0
        self.first_bad = self.first_good = None
        self.incident_id = None
        self.start = None
        self.detail = ""


class IncidentTracker:
    """Abre um incidente após N rodadas ruins seguidas e fecha após M boas."""

    def __init__(self, storage):
        self.storage = storage
        self._tracks = {}
        self.internet_ok = True   # usado para não culpar um site quando a internet caiu

    def _update(self, kind, target, is_bad, ts, detail, open_after, close_after):
        t = self._tracks.setdefault((kind, target), _Track())
        if is_bad:
            t.good, t.first_good = 0, None
            t.bad += 1
            if t.bad == 1:
                t.first_bad = ts
            t.detail = detail or t.detail
            if t.incident_id is None and t.bad >= open_after:
                t.start = t.first_bad
                t.incident_id = self.storage.open_incident(kind, target, t.first_bad, t.detail)
        else:
            t.bad = 0
            if t.incident_id is not None:
                t.good += 1
                if t.good == 1:
                    t.first_good = ts
                if t.good >= close_after:
                    self.storage.close_incident(t.incident_id, t.first_good)
                    t.incident_id, t.start, t.good = None, None, 0

    def evaluate_ping(self, ts, results):
        """results: {nome: (latência, perda)} de uma rodada de ping."""
        gw_lat, gw_loss = results.get(cfg.GATEWAY_NAME, (None, 100))
        dns = [results[t["name"]] for t in cfg.DNS_TARGETS if t["name"] in results]
        dns_down = sum(1 for _lat, loss in dns if loss >= 100)
        lats = [lat for lat, _loss in dns if lat is not None]
        avg_loss = sum(loss for _lat, loss in dns) / len(dns) if dns else 100
        med_lat = statistics.median(lats) if lats else None

        local_bad = gw_loss >= 100
        isp_bad = not local_bad and dns_down >= cfg.ISP_DOWN_MIN_TARGETS
        unstable = (not local_bad and not isp_bad and
                    (avg_loss >= cfg.INSTABILITY_LOSS_PCT or
                     (med_lat is not None and med_lat >= cfg.INSTABILITY_LATENCY_MS)))

        self._update(KIND_LOCAL, cfg.GATEWAY_NAME, local_bad, ts,
                     "Roteador/gateway não responde", cfg.OUTAGE_OPEN_AFTER, cfg.OUTAGE_CLOSE_AFTER)
        self._update(KIND_ISP, "DNS públicos", isp_bad, ts,
                     f"{dns_down} de {len(dns)} DNS sem resposta",
                     cfg.OUTAGE_OPEN_AFTER, cfg.OUTAGE_CLOSE_AFTER)
        detail = f"perda média {avg_loss:.0f}%" + (f", latência mediana {med_lat:.0f} ms" if med_lat else "")
        self._update(KIND_UNSTABLE, "DNS públicos", unstable, ts, detail,
                     cfg.INSTABILITY_OPEN_AFTER, cfg.INSTABILITY_CLOSE_AFTER)
        self.internet_ok = not (local_bad or isp_bad)

    def evaluate_http(self, ts, results):
        """results: {serviço: (ms, ok, detalhe)}. Só culpa o site se a internet está ok."""
        for name, (_ms, ok, detail) in results.items():
            is_bad = (not ok) and self.internet_ok
            self._update(KIND_SERVICE, name, is_bad, ts, detail,
                         cfg.SERVICE_OPEN_AFTER, cfg.SERVICE_CLOSE_AFTER)

    def active(self):
        """Incidentes abertos agora: [(tipo, alvo, início, detalhe)]."""
        return [(kind, target, t.start, t.detail)
                for (kind, target), t in self._tracks.items() if t.incident_id is not None]
