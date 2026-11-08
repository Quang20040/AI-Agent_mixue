"""Background job: after the Sunday deadline, the AI drafts next week's schedule for the manager.

Runs as one daemon thread per server process (started once from the dashboard). The job itself is
idempotent (staff_schedule.auto_schedule does nothing if the week already has a schedule), so a restart
or a second process cannot create two drafts. Disable with SCHEDULE_AUTO=0.
"""
from __future__ import annotations

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)
_LOCK = threading.Lock()
_STARTED = False
INTERVAL = int(os.environ.get('SCHEDULE_AUTO_INTERVAL', 300))


def enabled() -> bool:
    return str(os.environ.get('SCHEDULE_AUTO', '1')).strip().lower() not in {'0', 'false', 'off', 'no'}


def run_once():
    from src.engine import staff_schedule
    with _LOCK:
        try:
            plan = staff_schedule.auto_schedule()
            if plan:
                logger.info('auto schedule drafted %s', plan['plan_id'])
            return plan
        except Exception as exc:  # noqa: BLE001 - a failed run is retried next interval
            logger.warning('auto schedule failed: %s', exc)
            return None


def start() -> bool:
    global _STARTED
    if _STARTED or not enabled():
        return False
    _STARTED = True

    def loop():
        while True:
            run_once()
            time.sleep(INTERVAL)
    threading.Thread(target=loop, name='schedule-auto', daemon=True).start()
    return True
