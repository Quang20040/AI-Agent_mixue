"""Start Streamlit with the heavy libraries already imported.

Streamlit imports the app's modules on the first visit, so on a small server (Render Free has 0.1 CPU) the first
person to open the page waits for pandas, SQLAlchemy, LangGraph, Altair… to load. Importing them here, in the same
process, before the server starts moves that wait to boot time.
"""
import importlib
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PRELOAD = ('pandas', 'altair', 'openpyxl', 'PIL.Image', 'sqlalchemy', 'src.database', 'src.auth',
           'src.agent.mixue_agent', 'src.engine.vision_ocr', 'src.engine.day_sheet', 'src.engine.image_upload',
           'src.engine.daily_stock_service', 'src.dashboard.brand_ui', 'src.dashboard.shift_closing_ui')


def preload() -> None:
    started = time.monotonic()
    for name in PRELOAD:
        try:
            importlib.import_module(name)
        except Exception as exc:  # never block the server on a warm-up failure
            print(f'[serve] preload skipped {name}: {exc.__class__.__name__}', flush=True)
    print(f'[serve] preloaded {len(PRELOAD)} modules in {time.monotonic() - started:.1f}s', flush=True)


def log_memory(every=60):
    """One line a minute in the server log: resident memory and open browser sessions.

    Render restarts the service when it runs out of memory and shows only a 502 to visitors; this line makes
    the cause visible in Render Logs (a rising number before a restart)."""
    import threading

    def loop():
        while True:
            time.sleep(every)
            try:
                with open('/proc/self/status', encoding='ascii') as status:
                    rss = next(int(line.split()[1]) // 1024 for line in status if line.startswith('VmRSS'))
                sessions = '?'
                try:
                    from streamlit.runtime import Runtime
                    sessions = len(Runtime.instance()._session_mgr.list_active_sessions())
                except Exception:  # noqa: BLE001 - Streamlit internals may move between versions
                    pass
                print(f'[mem] rss={rss}MB sessions={sessions}', flush=True)
            except Exception:  # noqa: BLE001 - not on Linux, or /proc unavailable
                return

    threading.Thread(target=loop, daemon=True, name='memory-log').start()


if __name__ == '__main__':
    preload()
    log_memory()
    from streamlit.web import cli

    sys.argv = ['streamlit', 'run', os.path.join(ROOT, 'src', 'dashboard', 'app.py'), *sys.argv[1:]]
    sys.exit(cli.main())
