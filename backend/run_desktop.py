import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _load_conf() -> None:
    if getattr(sys, "frozen", False):
        conf = Path(sys.executable).resolve().parent / "planagent.conf"
    else:
        conf = Path(__file__).resolve().parent / "planagent.conf"
    if not conf.exists():
        return
    for raw in conf.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_conf()
os.environ.setdefault("PLANAGENT_AUTH_ENABLED", "false")

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402
from app.reminder import start_reminder_scheduler  # noqa: E402


def _open_browser() -> None:
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")


if __name__ == "__main__":
    # 启动桌面提醒
    start_reminder_scheduler()

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
