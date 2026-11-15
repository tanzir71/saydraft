"""Bounded, asynchronous Notes search and plain-text review inside the Hub."""

from concurrent.futures import ThreadPoolExecutor
import threading

from PySide6 import QtCore, QtWidgets

from saydraft.data.history_view import timestamp_label
from .private_text import PrivatePlainTextEdit


class NoteReads(QtCore.QObject):
    ready = QtCore.Signal(int, str, object)

    def __init__(self, store, parent):
        super().__init__(parent)
        self.store, self.closed = store, False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='notes-read')
        self._cancel = threading.Event()
        self._future = None
        parent.destroyed.connect(self.close)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.close)

    def read(self, generation, kind, value):
        if self.closed:
            return False
        self._cancel.set()
        if self._future is not None:
            self._future.cancel()
        cancel = self._cancel = threading.Event()
        def run():
            result = None
            try:
                if not cancel.is_set():
                    result = self.store.list(value, limit=200) if kind == 'list' else self.store.get(value)
            except Exception:
                pass  # No note content, search terms or database details in errors.
            if not self.closed and not cancel.is_set():
                try:
                    self.ready.emit(generation, kind, result)
                except RuntimeError:
                    pass
        try:
            self._future = self.executor.submit(run)
        except RuntimeError:
            return False
        return True

    def close(self):
        self.closed = True
        self._cancel.set()
        self.executor.shutdown(wait=False, cancel_futures=True)


class NotesPage(QtWidgets.QWidget):
    open_requested = QtCore.Signal(str)
    new_requested = QtCore.Signal()

    def __init__(self, store):
        super().__init__()
        self.store, self.rows, self.current_note = store, (), None
        self._generation = 0
        self.jobs = NoteReads(store, self)
        self.jobs.ready.connect(self._accept, QtCore.Qt.QueuedConnection)
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self.refresh)
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel('Notes')
        title.setProperty('role', 'display')
        layout.addWidget(title)
        description = QtWidgets.QLabel('Your Scratchpad notes, saved on this PC.')
        layout.addWidget(description)
        toolbar = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setAccessibleName('Search Notes')
        self.search.setPlaceholderText('Search your notes…')
        self.search.setMaxLength(512)
        self.search.textChanged.connect(self._search_changed)
        toolbar.addWidget(self.search, 1)
        self.refresh_button = QtWidgets.QPushButton('Refresh')
        self.refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.refresh_button)
        self.new_button = QtWidgets.QPushButton('New note')
        self.new_button.setProperty('primary', True)
        self.new_button.clicked.connect(lambda: self.new_requested.emit())
        toolbar.addWidget(self.new_button)
        layout.addLayout(toolbar)
        split = QtWidgets.QSplitter()
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setAccessibleName('Saved notes')
        self.list_widget.setWordWrap(True)
        self.list_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.list_widget.setTextElideMode(QtCore.Qt.ElideRight)
        self.list_widget.currentRowChanged.connect(self._select)
        self.list_widget.itemDoubleClicked.connect(self._open_item)
        split.addWidget(self.list_widget)
        self.editor = PrivatePlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setAccessibleName('Saved note text')
        self.editor.setPlaceholderText('Choose a note to read it here.')
        split.addWidget(self.editor)
        split.setStretchFactor(1, 2)
        layout.addWidget(split, 1)
        self.status = QtWidgets.QLabel('No notes saved yet. Choose New note to start.')
        self.status.setTextFormat(QtCore.Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.open_button = QtWidgets.QPushButton('Open in Scratchpad')
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_note)
        layout.addWidget(self.open_button, alignment=QtCore.Qt.AlignLeft)

    def _clear_detail(self):
        self.current_note = None
        self.editor.clear()
        self.open_button.setEnabled(False)

    def _search_changed(self):
        self._generation += 1
        self.rows = ()
        self.list_widget.clear()
        self._clear_detail()
        self.status.setText('Searching…')
        self.timer.start()

    def refresh(self):
        self.timer.stop()
        self._generation += 1
        self.rows = ()
        self.list_widget.clear()
        self._clear_detail()
        self.status.setText('Loading notes…')
        if not self.jobs.read(self._generation, 'list', self.search.text()):
            self._accept(self._generation, 'list', None)

    def _select(self, index):
        self._generation += 1
        self._clear_detail()
        if 0 <= index < len(self.rows):
            self.status.setText('Loading note…')
            if not self.jobs.read(self._generation, 'detail', self.rows[index].id):
                self._accept(self._generation, 'detail', None)

    @QtCore.Slot(int, str, object)
    def _accept(self, generation, kind, result):
        if self.jobs.closed or generation != self._generation:
            return
        if result is None:
            self.status.setText('Could not read Notes. Try Refresh.' if kind == 'list' else
                'This note is unavailable. Try Refresh.')
            return
        if kind == 'list':
            self.rows = result
            self.list_widget.blockSignals(True)
            self.list_widget.clear()
            for note in result:
                lines = [' '.join(line.split()) for line in note.preview.splitlines() if line.strip()]
                if lines and lines[0][:100] == note.title:
                    lines = lines[1:]
                preview = lines[0][:90] if lines else ''
                self.list_widget.addItem(note.title + ('\n' + preview if preview else ''))
            self.list_widget.blockSignals(False)
            self.status.setText(f'{len(result)} recent matching notes (up to 200).' if result else
                'No matching notes.' if self.search.text() else 'No notes saved yet. Choose New note to start.')
        else:
            self.current_note = result
            self.editor.setPlainText(result.body)
            self.open_button.setEnabled(True)
            origin = {'scratchpad': 'Scratchpad', 'command': 'Command', 'ask': 'Ask', 'meeting': 'Meeting'}[result.kind]
            self.status.setText(f'Saved {timestamp_label(result.updated_at)} · {origin}')

    def open_note(self):
        if self.current_note is not None:
            self.open_requested.emit(self.current_note.id)

    def _open_item(self, item):
        index = self.list_widget.row(item)
        if 0 <= index < len(self.rows):
            self.open_requested.emit(self.rows[index].id)
