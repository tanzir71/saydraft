"""One persistent Hub window for application pages and shared Settings controls."""

from PySide6 import QtCore, QtWidgets

from .home_page import HomePage
from .history_page import HistoryPage
from .settings_page import SettingsPage
from .icons import line_icon


_ICONS = {
    "Home": '<path d="M3 9 10 3l7 6M5 8v9h10V8M8 17v-5h4v5"/>',
    "History": '<circle cx="10" cy="10" r="7"/><path d="M10 6v4l3 2"/>',
    "Dictionary": '<path d="M10 5C8 3 4 3 2 4v12c3-1 6-1 8 1 2-2 5-2 8-1V4c-3-1-6-1-8 1v12"/>',
    "Snippets": '<rect x="3" y="3" width="14" height="14" rx="2"/><path d="M6 7h8M6 10h5M6 13h7"/>',
    "Style": '<path d="m4 17 6-14 6 14M6 12h8"/>',
    "Notes": '<path d="M4 2h8l4 4v12H4V2m8 0v4h4M7 10h6M7 13h6"/>',
    "Settings": '<path d="M3 5h14M3 10h14M3 15h14"/><circle cx="7" cy="5" r="2"/><circle cx="13" cy="10" r="2"/><circle cx="8" cy="15" r="2"/>',
}


class HubWindow(QtWidgets.QWidget):
    def __init__(self, *, settings_options, history_options, shortcut=lambda: "Ctrl+Win", model=lambda: "",
                 tier=lambda: "pending", settings_page_factory=SettingsPage, history_page_factory=HistoryPage):
        super().__init__()
        self.setWindowTitle("Saydraft")
        self.resize(1080, 720)
        self.setMinimumSize(880, 600)
        settings_options = dict(settings_options)
        database = getattr(history_options.get("store"), "db_path", None)
        if database is not None:
            settings_options.setdefault("snippets_db_path", database)
        self.settings_page = settings_page_factory(**settings_options)
        history_options = dict(history_options)
        history_options.setdefault("glossary_path", self.settings_page.glossary_path)
        self.history_page = history_page_factory(**history_options)
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)
        rail = QtWidgets.QVBoxLayout()
        wordmark = QtWidgets.QLabel("Saydraft")
        wordmark.setProperty("role", "display")
        rail.addWidget(wordmark)
        self.navigation = QtWidgets.QListWidget()
        self.navigation.setAccessibleName("Hub pages")
        self.navigation.setFixedWidth(164)
        self.navigation.setIconSize(QtCore.QSize(20, 20))
        for name in _ICONS:
            self.navigation.addItem(name)
        rail.addWidget(self.navigation, 1)
        root.addLayout(rail)
        body = QtWidgets.QVBoxLayout()
        self.pages = QtWidgets.QStackedWidget()
        body.addWidget(self.pages, 1)
        self.home_page = HomePage(self.history_page.store, shortcut=shortcut, model=model, tier=tier)
        self.home_page.history_requested.connect(self._open_history_row)
        self.home_page.privacy_requested.connect(lambda: self.show_page("Settings", tab="Privacy"))
        self.history_view = QtWidgets.QScrollArea()
        self.history_view.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.history_view.setWidgetResizable(True)
        self.history_view.setWidget(self.history_page)
        self.page_widgets = {"Home": self.home_page, "History": self.history_view}
        for name in ("Dictionary", "Snippets", "Style"):
            for index in range(self.settings_page.tabs.count()):
                if self.settings_page.tabs.tabText(index) == name:
                    page = self.settings_page.tabs.widget(index)
                    self.settings_page.tabs.removeTab(index)
                    self.page_widgets[name] = page
                    break
        self.settings_page.sync_sections()
        notes = QtWidgets.QWidget()
        note_layout = QtWidgets.QVBoxLayout(notes)
        title = QtWidgets.QLabel("Notes")
        title.setProperty("role", "display")
        note_layout.addWidget(title)
        note_layout.addWidget(QtWidgets.QLabel("No notes saved yet."))
        note_layout.addStretch()
        self.page_widgets.update(Notes=notes, Settings=self.settings_page)
        for name in _ICONS:
            self.pages.addWidget(self.page_widgets[name])
        self.footer = QtWidgets.QWidget()
        footer = QtWidgets.QHBoxLayout(self.footer)
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addWidget(self.settings_page.status_label, 1)
        self.save_button = QtWidgets.QPushButton("Save changes")
        self.save_button.setProperty("primary", True)
        self.save_button.clicked.connect(self._save)
        footer.addWidget(self.save_button)
        body.addWidget(self.footer)
        self.settings_page.apply_button.hide()
        self.settings_page.close_button.hide()
        root.addLayout(body, 1)
        self.navigation.currentRowChanged.connect(self._navigate)
        self.icon_timer = QtCore.QTimer(self)
        self.icon_timer.setSingleShot(True)
        self.icon_timer.timeout.connect(self._refresh_icons)
        self._refresh_icons()
        self.show_page("Home")

    def _refresh_icons(self):
        for index, paths in enumerate(_ICONS.values()):
            self.navigation.item(index).setIcon(line_icon(paths, self.navigation.palette()))
        self.home_page.refresh_status()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QtCore.QEvent.PaletteChange, QtCore.QEvent.StyleChange) and hasattr(self, "icon_timer"):
            self.icon_timer.start(0)

    def _navigate(self, index):
        if index < 0:
            return
        self.pages.setCurrentIndex(index)
        name = self.navigation.item(index).text()
        self.footer.setVisible(name in ("Dictionary", "Snippets", "Style", "Settings"))
        if name == "Home":
            self.home_page.refresh()
        elif name == "History":
            self.history_page.refresh()
        elif name == "Settings":
            self.settings_page.refresh_privacy()

    def show_page(self, name="Home", *, tab=None):
        names = list(_ICONS)
        index = names.index(name)
        if self.navigation.currentRow() == index:
            self._navigate(index)
        else:
            self.navigation.setCurrentRow(index)
        if name == "Settings" and tab:
            self.settings_page.show_tab(tab)

    def _open_history_row(self, row_id):
        self.show_page("History")
        self.history_page.search_edit.clear()
        self.history_page._select_id(row_id)

    def _save(self):
        if self.settings_page.apply_changes():
            self.home_page.refresh()

    def refresh(self):
        self.history_page.refresh()
        self.home_page.refresh()

    def closeEvent(self, event):
        self.settings_page.pause_downloads()
        super().closeEvent(event)
