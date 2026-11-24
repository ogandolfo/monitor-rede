"""Inicia o Monitor de Rede: liga a coleta imediatamente e depois sobe o painel.

Assim o histórico é gravado mesmo que ninguém abra a página (ex.: ao ligar o PC).
Uso:  python run.py            (com janela)
      pythonw run.py --server.headless true   (em segundo plano; usado na inicialização)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Sem console (pythonw), manda as mensagens para data/netmon.log
if sys.stdout is None or sys.stderr is None:
    log_path = ROOT / "data" / "netmon.log"
    log_path.parent.mkdir(exist_ok=True)
    if log_path.exists() and log_path.stat().st_size > 5_000_000:
        log_path.unlink()
    log = open(log_path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = sys.stdout or log
    sys.stderr = sys.stderr or log

from netmon.collector import AlreadyRunning, get_global_collector  # noqa: E402

try:
    get_global_collector()
except AlreadyRunning:
    print("O monitor já está rodando. Abra http://localhost:8501")
    sys.exit(1)

from streamlit.web import cli  # noqa: E402

sys.argv = ["streamlit", "run", str(ROOT / "monitor.py"), *sys.argv[1:]]
sys.exit(cli.main())
