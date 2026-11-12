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
    _settled = QtCore.Signal()
    _active = set()

    def __init__(self, parent=None):
        # The window may disappear while Python is still downloading. Keep the
        # signal source alive independently until the worker really exits.
        super().__init__()
        self.pause_event = threading.Event()
        self._thread = None
        self._settled.connect(self._complete, QtCore.Qt.ConnectionType.QueuedConnection)
        if parent is not None:
            parent.destroyed.connect(self.pause)
        app = QtCore.QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.pause)

    @QtCore.Slot()
    def pause(self):
        self.pause_event.set()

    def start(self, action):
        if self._thread is not None:
            raise RuntimeError("Download task can only start once")
        def run():
            try:
                result = action(self.progress.emit)
                self.succeeded.emit(str(result or ""))
            except DownloadPaused as error:
                self.paused.emit(str(error))
            except Exception as error:
                self.failed.emit(str(error))
            finally:
                self._settled.emit()

        self._thread = threading.Thread(target=run, name="Saydraft-model-download", daemon=True)
        self._active.add(self)
        try:
            self._thread.start()
        except BaseException:
            if not self._thread.is_alive():
                self._active.discard(self)
                self.deleteLater()
            else:
                self.pause()
            raise

    @QtCore.Slot()
    def _complete(self):
        if self._thread.is_alive():
            QtCore.QTimer.singleShot(1, self._complete)
            return
        self.finished.emit()  # GUI thread, after no worker can emit from this object.
        self._active.discard(self)
        self.deleteLater()
