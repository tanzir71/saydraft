"""Serial background browsing and independent cancellable History export."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

from PySide6 import QtCore, QtWidgets

from saydraft.data.history_view import save_history_export


class HistoryJobs(QtCore.QObject):
    ready = QtCore.Signal(int, object)
    exported = QtCore.Signal(int, object)

    def __init__(self, store, parent):
        super().__init__(parent)
        self.store, self.closed, self._view = store, False, None
        self._reader = ThreadPoolExecutor(max_workers=1, thread_name_prefix="history-read")
        self._writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="history-export")
        self._read_cancel, self._export_cancel = threading.Event(), threading.Event()
        self._read_future = self._export_future = None
        parent.destroyed.connect(self.close)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.close)

    def cancel_read(self):
        self._read_cancel.set()
        if self._read_future is not None:
            self._read_future.cancel()

    def _read(self, generation, action):
        if self.closed:
            return False
        self.cancel_read()
        cancelled = self._read_cancel = threading.Event()
        def run():
            result = None
            try:
                if not cancelled.is_set():
                    result = action(cancelled)
            except Exception:
                pass  # Errors never expose transcripts, search terms or provider details.
            finally:
                if self.closed:
                    self._view = None
            if not self.closed and not cancelled.is_set():
                try:
                    self.ready.emit(generation, result)
                except RuntimeError:
                    pass  # The owned page was destroyed after admission.
        self._read_future = self._reader.submit(run)
        return True

    def page(self, generation, *, fresh, **options):
        def action(cancelled):
            if fresh:
                self._view = None
            if self._view is None:
                self._view = self.store.snapshot(cancelled=cancelled.is_set)
            result = self._view.search_page(cancelled=cancelled.is_set, **options)
            return "page", result, self._view
        return self._read(generation, action)

    def detail(self, generation, view, row_id):
        return self._read(generation, lambda cancelled:
            ("detail", view.get_row(row_id, cancelled=cancelled.is_set), view))

    @property
    def export_busy(self):
        return self._export_future is not None and not self._export_future.done()

    def export(self, generation, view, path, *, query, ceiling_id, format):
        if self.closed or self.export_busy:
            return False
        cancelled = self._export_cancel = threading.Event()
        def run():
            rows, outcome = None, ("error", 0)
            try:
                target = Path(path).resolve()
                protected = [Path(self.store.db_path).resolve(), view.db_path.resolve()]
                protected += [Path(str(item) + suffix) for item in list(protected)
                    for suffix in ("-wal", "-shm", "-journal")]
                if target in protected:
                    raise ValueError("Export cannot replace its History database")
                rows = view.iter_filtered(query=query, ceiling_id=ceiling_id, cancelled=cancelled.is_set)
                count = save_history_export(path, rows, format, cancelled=cancelled.is_set)
                outcome = "success", count
            except Exception:
                outcome = ("cancelled" if cancelled.is_set() else "error"), 0
            finally:
                if rows is not None:
                    rows.close()
            if not self.closed:
                try:
                    self.exported.emit(generation, outcome)
                except RuntimeError:
                    pass
        self._export_future = self._writer.submit(run)
        return True

    def cancel_export(self):
        self._export_cancel.set()

    @QtCore.Slot()
    def close(self):
        if not self.closed:
            self.closed = True
            self.cancel_read()
            self.cancel_export()
            self._view = None
            self._reader.shutdown(wait=False, cancel_futures=True)
            self._writer.shutdown(wait=False, cancel_futures=True)
