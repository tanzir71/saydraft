"""Download work runs outside Qt; progress returns through queued signals."""

import threading
import inspect

from PySide6 import QtCore

from saydraft.models.downloader import DownloadPaused


def call_download(callback, *args, pause_event):
    """Keep the old injectable callback API while built-in transfers support pause."""
    parameters = inspect.signature(callback).parameters
    supports_pause = "pause_event" in parameters or any(
        item.kind == inspect.Parameter.VAR_KEYWORD for item in parameters.values())
    return callback(*args, **({"pause_event": pause_event} if supports_pause else {}))


class DownloadTask(QtCore.QObject):
    progress = QtCore.Signal(int)
    succeeded = QtCore.Signal(str)
    failed = QtCore.Signal(str)
    paused = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pause_event = threading.Event()

    def pause(self):
        self.pause_event.set()

    def start(self, action):
        def run():
            try:
                result = action(self.progress.emit)
                self.succeeded.emit(str(result or ""))
            except DownloadPaused as error:
                self.paused.emit(str(error))
            except Exception as error:
                self.failed.emit(str(error))
            finally:
                self.finished.emit()

        self._thread = threading.Thread(target=run, name="Saydraft-model-download", daemon=True)
        self._thread.start()
