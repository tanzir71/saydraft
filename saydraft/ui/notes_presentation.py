from PySide6 import QtCore, QtWidgets
from .kit import Card, Label, PageHeader
from .presentation import rebuild, style_list, show


def arrange_notes(page):
    root = rebuild(page, margins=(40, 24, 40, 28), spacing=20)
    page.search.setProperty("search", True)
    root.addWidget(PageHeader("Notes", "Your Scratchpad notes, saved on this PC.",
        actions=(show(page.search), show(page.refresh_button), show(page.new_button))))
    page.split = QtWidgets.QSplitter()
    page.split.setChildrenCollapsible(False)
    page.split.setHandleWidth(16)
    left, right = Card(), Card(padding=24)
    style_list(page.list_widget)
    left.body.addWidget(show(page.list_widget), 1)
    page.note_title = Label("Choose a note", "heading")
    right.body.setSpacing(16)
    right.body.addWidget(page.note_title)
    page.editor.setProperty("reader", True)
    page.editor.setProperty("role", "body")
    page.editor.setProperty("fontRatio", 15 / 14)
    right.body.addWidget(show(page.editor), 1)
    right.body.addWidget(show(page.open_button), alignment=QtCore.Qt.AlignLeft)
    page.split.addWidget(left)
    page.split.addWidget(right)
    page.split.setSizes([300, 520])
    page.split.setStretchFactor(1, 1)
    root.addWidget(page.split, 1)
    root.addWidget(show(page.status))
