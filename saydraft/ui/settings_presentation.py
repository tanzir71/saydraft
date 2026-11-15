"""Presentation-only assembly of the nine Settings sections."""
from PySide6 import QtCore, QtWidgets
from .kit import Card, Label, SettingsGroup, ActionButton, control_row
from .reflow import AdaptiveRow
from .presentation import rebuild, section, group, show, general, cleanup, SettingsNavigation


def disclosure(title, widget):
    frame = Card(padding=16)
    button = ActionButton(title + "  ↓", ghost=True)
    button.setCheckable(True)
    button.setAccessibleDescription("Expand or collapse " + title)
    frame.body.setSpacing(12)
    frame.body.addWidget(button)
    frame.body.addWidget(widget)
    widget.hide()
    button.toggled.connect(widget.setVisible)
    frame.expand_button = button
    return frame


def arrange_settings(s):
    wrappers = {s.tabs.tabText(i): s.tabs.widget(i) for i in range(s.tabs.count())}
    def inner(name):
        return wrappers[name].widget() if isinstance(wrappers[name], QtWidgets.QScrollArea) else wrappers[name]
    general(s, inner("General"))
    cleanup(s, inner("Cleanup"))
    s.tier_combo.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
    s.tier_combo.setMinimumWidth(0)
    # Move the existing controls, retaining public aliases and all worker wiring.
    performance = wrappers["Performance"]
    s.tabs.removeTab(s.tabs.indexOf(performance))
    models = inner("Models")
    layout = section(models, "Models", "Download once. Dictate offline. Review size and license before downloading.")
    for title, widgets in (("Performance tier", (s.tier_picker,)), ("Speech recognition", (s.model_picker,)),
            ("AI cleanup", (s.llm_enabled_checkbox, s.cleanup_picker)),
            ("Speech detection", (s.vad_license, s.vad_download_button, s.model_progress)),
            ("Storage", (s.model_storage,))):
        card = Card(padding=20)
        card.body.setSpacing(12)
        card.body.addWidget(Label(title, "subheading"))
        for widget in widgets:
            card.body.addWidget(show(widget))
        layout.addWidget(card)
    advanced = QtWidgets.QWidget()
    form = QtWidgets.QFormLayout(advanced)
    form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
    for caption, widget in (("Speech device", s.device_combo), ("Compute type", s.compute_combo),
                           ("Local files only", s.local_files_checkbox), ("GGUF model path", s.llm_path_edit)):
        form.addRow(caption, show(widget))
    layout.addWidget(disclosure("Advanced model options", advanced))
    s.performance_disclosure = disclosure("Hardware and performance", performance)
    layout.addWidget(s.performance_disclosure)
    layout.addStretch(1)

    languages = s.languages_page
    layout = section(languages, "Languages", "Auto-detect, or pin up to three languages you use most.")
    group(layout, "Recognition", [("Choose the model automatically", languages.routing, "Changing languages never downloads a model.")])
    pins = SettingsGroup("Pinned languages")
    for i, combo in enumerate(languages.combos, 1):
        pins.add_row(f"Language {i}", show(combo), "Auto detects the language." if i == 1 else "Optional")
    from .language_tiles import LanguageTiles
    languages.tiles = LanguageTiles(languages)
    layout.addWidget(languages.tiles)
    layout.addWidget(disclosure("Language pin order", pins))
    group(layout, "English", [("English max", languages.english_max, "Use Parakeet v2 when English is the only pinned language.")])
    notice = Card(padding=20)
    notice.body.addWidget(show(languages.note))
    layout.addWidget(notice)
    layout.addStretch(1)

    microphone = s.microphone_page
    whisper = microphone.whisper_controls
    # Physically move Whisper to Labs; microphone_page.whisper_controls remains valid.
    s.labs_page.layout().insertWidget(0, whisper)
    whisper.show()
    from .grouped_settings import microphone as arrange_microphone, privacy as arrange_privacy, shortcuts
    arrange_microphone(microphone)
    shortcuts(s, inner("Shortcuts"))
    # Remove the legacy duplicate heading only.
    for label in microphone.findChildren(QtWidgets.QLabel, options=QtCore.Qt.FindDirectChildrenOnly):
        if label.text() == "Microphone":
            label.hide()
    privacy = s.privacy_page
    updates = privacy.updates_card
    privacy.layout().removeWidget(updates)
    arrange_privacy(privacy)
    about = inner("About")
    layout = section(about, "About", "Saydraft · private, on-device voice typing for Windows.")
    card = Card(padding=24)
    card.body.setSpacing(12)
    card.body.addWidget(Label("Saydraft", "display"))
    from saydraft import __version__
    card.body.addWidget(Label("Version " + __version__ + " · unsigned distribution", "mono"))
    card.body.addWidget(Label("Made by Tanzir. Open source under the MIT license.", "muted"))
    from PySide6 import QtGui
    links=[]
    for caption, url in (("GitHub", "https://github.com/tanzir71/saydraft"),
                         ("Website", "https://tanzir71.github.io/saydraft/")):
        button = ActionButton(caption,icon="external",ghost=True,small=True)
        button.setAccessibleName("Open Saydraft " + caption)
        button.clicked.connect(lambda _checked=False,url=url: QtGui.QDesktopServices.openUrl(QtCore.QUrl(url)))
        links.append(button)
    card.body.addWidget(control_row(*links))
    layout.addWidget(card)
    layout.addWidget(updates)
    updates.show()
    layout.addStretch(1)

    labs = s.labs_page
    extras = [w for w in labs.findChildren(QtWidgets.QGroupBox, options=QtCore.Qt.FindDirectChildrenOnly)
              if w not in (labs.command, whisper)]
    layout = section(labs, "Labs", "Experimental features. You choose what to enable.")
    whisper.setTitle("")
    whisper.layout().insertWidget(0, Label("Whisper mode · quiet speech", "subheading"))
    layout.addWidget(show(whisper))
    preview = Card(padding=20)
    preview.body.setSpacing(12)
    preview.body.addWidget(Label("English live preview", "subheading"))
    for widget in (labs.description, labs.license, labs.eligibility, labs.live, labs.streaming):
        preview.body.addWidget(show(widget))
    preview.body.addWidget(control_row(show(labs.download), show(labs.pause_button)))
    preview.body.addWidget(show(labs.progress))
    preview.body.addWidget(labs.progress.caption)
    preview.body.addWidget(show(labs.status))
    layout.addWidget(preview)
    labs.command.setTitle("")
    labs.command.layout().insertWidget(0, Label("Command, Translate and Ask", "subheading"))
    layout.addWidget(show(labs.command))
    for widget in extras:
        layout.addWidget(show(widget))
    layout.addStretch(1)
    # Order the nine sections, retaining extracted personalization pages until Hub takes them.
    names = ("General", "Shortcuts", "Microphone", "Models", "Languages", "Cleanup", "Privacy", "Labs", "About",
             "Dictionary", "Snippets", "Style")
    for i, name in enumerate(names):
        s.tabs.tabBar().moveTab(s.tabs.indexOf(wrappers[name]), i)
    layout = rebuild(s, margins=(28, 24, 40, 28))
    s.section_navigation = SettingsNavigation(s)
    s.section_body = QtWidgets.QBoxLayout(QtWidgets.QBoxLayout.LeftToRight)
    s.section_body.setSpacing(32)
    s.section_body.addWidget(s.section_navigation)
    s.section_body.addWidget(s.tabs, 1)
    layout.addLayout(s.section_body, 1)
    footer = AdaptiveRow()
    footer.addWidget(show(s.status_label), 1)
    footer.addWidget(show(s.apply_button))
    footer.addWidget(show(s.close_button))
    layout.addLayout(footer)
    s.section_combo.hide()
    s.tabs.show()
