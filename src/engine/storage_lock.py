"""Reentrant thread and process lock for a local JSON read/modify/write transaction."""

import os
import threading
import time


class FileTransactionLock:
    def __init__(self, path_factory, timeout=15):
        self.path_factory = path_factory
        self.timeout = timeout
        self.thread_lock = threading.RLock()
        self.local = threading.local()

    def __enter__(self):
        self.thread_lock.acquire()
        depth = getattr(self.local, "depth", 0)
        if depth:
            self.local.depth = depth + 1
            return self
        handle = None
        try:
            path = self.path_factory()
            path.parent.mkdir(parents=True, exist_ok=True)
            handle = path.open("a+b")
            if handle.seek(0, 2) == 0:
                handle.write(b"0")
                handle.flush()
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Kho dữ liệu đang bận; chưa ghi thay đổi. Hãy thử lại.") from None
                    time.sleep(0.05)
            self.local.handle = handle
            self.local.depth = 1
            return self
        except BaseException:
            if handle:
                handle.close()
            self.thread_lock.release()
            raise

    def __exit__(self, *exc):
        self.local.depth -= 1
        try:
            if self.local.depth == 0:
                handle = self.local.handle
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                finally:
                    handle.close()
        finally:
            self.thread_lock.release()
