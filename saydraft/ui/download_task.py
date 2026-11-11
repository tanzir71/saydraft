"""Download work runs outside Qt; progress returns through queued signals."""

import threading

from PySide6 import QtCore


class DownloadTask(QtCore.QObject):
    progress = QtCore.Signal(int)
    succeeded = QtCore.Signal(str)
    failed = QtCore.Signal(str)
    finished = QtCore.Signal()

    def start(self, action):
        def run():
            try:
                result = action(self.progress.emit)
                self.succeeded.emit(str(result or ""))
            except Exception as error:
                self.failed.emit(str(error))
            finally:
                self.finished.emit()

        self._thread = threading.Thread(target=run, name="Saydraft-model-download", daemon=True)
        self._thread.start()
