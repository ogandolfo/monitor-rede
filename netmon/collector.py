"""Coletor em segundo plano: roda as sondas, guarda o histórico e detecta incidentes."""
import datetime as dt
import os
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from . import config as cfg
from . import credentials
from .incidents import KIND_MONITOR_OFF, IncidentTracker
from .probes import check_service, fetch_ssh_metrics, ping_host
from .storage import Storage


class AlreadyRunning(RuntimeError):
    pass


def acquire_instance_lock():
    """Garante um único monitor gravando no banco (ex.: tarefa do Windows + .bat)."""
    if getattr(sys, "_netmon_lock", None) is not None:   # já é deste processo
        return
    import msvcrt
    cfg.LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = open(cfg.LOCK_PATH, "a+")  # noqa: SIM115 — mantido aberto até o processo terminar
    try:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        fh.close()
        raise AlreadyRunning("Outra instância do monitor já está rodando neste computador.")
    sys._netmon_lock = fh


def get_global_collector():
    """Um único coletor por processo, criado na primeira chamada.

    Fica guardado em `sys` para sobreviver aos recarregamentos de módulo do Streamlit.
    """
    lock = sys.__dict__.setdefault("_netmon_collector_lock", threading.Lock())
    with lock:
        collector = getattr(sys, "_netmon_collector", None)
        if collector is None:
            collector = Collector()
            sys._netmon_collector = collector
        return collector


class Collector:
    def __init__(self):
        acquire_instance_lock()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ssh_wake = threading.Event()
        self._pool = ThreadPoolExecutor(max_workers=len(cfg.PING_TARGETS) + len(cfg.SERVICES))

        self.storage = Storage(cfg.DB_PATH)
        self.tracker = IncidentTracker(self.storage)
        self._register_downtime()

        self.ping_latest = {}
        self.http_latest = {}
        self.ping_history = deque(maxlen=cfg.PING_LIVE_POINTS)   # (datetime, {nome: (lat, perda)})
        self.http_history = deque(maxlen=cfg.HTTP_LIVE_POINTS)   # (datetime, {nome: (ms, ok)})
        self.last_ping = None
        self.last_http = None
        self._minute_bucket = None
        self._minute_acc = {}
        self._last_prune = 0.0

        user = os.getenv("ONT_USER", "")
        credentials.migrate_ont_password_from_env(user)
        password, self.ssh_pass_source = credentials.get_ont_password(user)
        self.ssh_creds = (os.getenv("ONT_IP", ""), user, password)
        self.ssh_latest = None
        self.ssh_last_time = None
        self.ssh_history = deque(maxlen=cfg.SSH_LIVE_POINTS)

        for target, name in ((self._ping_loop, "ping"), (self._http_loop, "http"),
                             (self._ssh_loop, "ssh")):
            threading.Thread(target=target, name=f"netmon-{name}", daemon=True).start()

    def stop(self):
        self._stop.set()
        self._ssh_wake.set()
        self._pool.shutdown(wait=False, cancel_futures=True)
        self._flush_minute()

    # --- início: registra o período em que o monitor ficou desligado ------
    def _register_downtime(self):
        now = int(time.time())
        last = self.storage.last_beat()
        if last is not None:
            self.storage.close_dangling_incidents(last)
            if now - last >= cfg.MONITOR_GAP_S:
                self.storage.add_closed_incident(
                    KIND_MONITOR_OFF, "Monitor", last, now,
                    "Sem dados neste período (PC desligado ou monitor fechado)")
        self.storage.beat(now)

    # --- ping --------------------------------------------------------------
    def _accumulate_minute(self, ts, results):
        bucket = ts // 60 * 60
        if self._minute_bucket is not None and bucket != self._minute_bucket:
            self._flush_minute()
        self._minute_bucket = bucket
        for name, (lat, loss) in results.items():
            acc = self._minute_acc.setdefault(name, ([], []))
            if lat is not None:
                acc[0].append(lat)
            acc[1].append(loss)

    def _flush_minute(self):
        if self._minute_bucket is None or not self._minute_acc:
            return
        rows = []
        for name, (lats, losses) in self._minute_acc.items():
            rows.append((
                self._minute_bucket, name,
                round(sum(lats) / len(lats), 2) if lats else None,
                max(lats) if lats else None,
                round(sum(losses) / len(losses), 2),
                len(losses),
            ))
        self._minute_acc = {}
        try:
            self.storage.add_ping_minutes(rows)
        except Exception:  # noqa: BLE001 — não derruba a coleta por erro de disco
            pass

    def _ping_once(self):
        futs = {t["name"]: self._pool.submit(ping_host, t["ip"]) for t in cfg.PING_TARGETS}
        results = {name: f.result() for name, f in futs.items()}
        now = dt.datetime.now()
        ts = int(now.timestamp())
        with self._lock:
            self.ping_latest = results
            self.ping_history.append((now, results))
            self.last_ping = now
            self._accumulate_minute(ts, results)
            self.tracker.evaluate_ping(ts, results)
        self.storage.beat(ts)
        if time.time() - self._last_prune > 86400:
            self.storage.prune(cfg.RETENTION_DAYS)
            self._last_prune = time.time()

    def _ping_loop(self):
        self._run_every(cfg.PING_INTERVAL_S, self._ping_once)

    # --- HTTP --------------------------------------------------------------
    def _http_once(self):
        futs = {s["name"]: self._pool.submit(check_service, s["url"]) for s in cfg.SERVICES}
        results = {name: f.result() for name, f in futs.items()}
        now = dt.datetime.now()
        ts = int(now.timestamp())
        with self._lock:
            self.http_latest = results
            self.http_history.append((now, {n: (ms, ok) for n, (ms, ok, _d) in results.items()}))
            self.last_http = now
            self.tracker.evaluate_http(ts, results)
        self.storage.add_http_samples(
            [(ts, n, ms, int(ok), d) for n, (ms, ok, d) in results.items()])

    def _http_loop(self):
        self._run_every(cfg.HTTP_INTERVAL_S, self._http_once)

    def _run_every(self, interval, fn):
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                fn()
            except RuntimeError:      # pool encerrado durante o stop()
                return
            except Exception:  # noqa: BLE001 — uma rodada com erro não para o monitor
                pass
            self._stop.wait(max(0.0, interval - (time.monotonic() - started)))

    # --- SSH ---------------------------------------------------------------
    def set_ssh_credentials(self, ip, user, password=None):
        """password=None mantém a senha atual. Senhas novas vão para o Gerenciador de Credenciais."""
        if password:
            try:
                credentials.set_ont_password(user, password)
                source = "keyring"
            except Exception:  # noqa: BLE001
                source = "memória"
        else:
            password, source = credentials.get_ont_password(user)
            if not password:
                password, source = self.ssh_creds[2], self.ssh_pass_source
        with self._lock:
            self.ssh_creds = (ip, user, password)
            self.ssh_pass_source = source
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
                ok = not data.get("error") and data["CPU_Pct"] is not None and data["Memoria_Pct"] is not None
                if ok:
                    self.ssh_history.append((now, data["CPU_Pct"], data["Memoria_Pct"]))
            if ok:
                self.storage.add_ssh_sample(int(now.timestamp()), data["CPU_Pct"], data["Memoria_Pct"])
            self._ssh_wake.wait(cfg.SSH_INTERVAL_S)
            self._ssh_wake.clear()

    # --- leitura para a interface -----------------------------------------
    def snapshot(self):
        with self._lock:
            return {
                "ping_latest": dict(self.ping_latest),
                "http_latest": dict(self.http_latest),
                "ping_history": list(self.ping_history),
                "http_history": list(self.http_history),
                "last_ping": self.last_ping,
                "last_http": self.last_http,
                "active_incidents": self.tracker.active(),
                "ssh_ip": self.ssh_creds[0],
                "ssh_user": self.ssh_creds[1],
                "ssh_pass_source": self.ssh_pass_source,
                "ssh_latest": self.ssh_latest,
                "ssh_last_time": self.ssh_last_time,
                "ssh_history": list(self.ssh_history),
            }
