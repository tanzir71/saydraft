"""Setup chrome, using the wizard's native navigation and existing staged pages."""
from PySide6 import QtCore, QtGui, QtWidgets
from .kit import Card, Label, Badge, Segmented, control_row
from .theme.style import color, bar_color, role_font, scaled, high_contrast, repolish
from .presentation import rebuild
from .reflow import AdaptiveRow


class StepMarker(QtWidgets.QWidget):
    def __init__(self, number, parent=None):
        super().__init__(parent)
        self.number, self.state = number, "upcoming"
        self.setFixedSize(28, 28)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        circle = QtCore.QRectF(2, 2, self.width()-4, self.height()-4)
        current, done = self.state == "current", self.state == "done"
        p.setPen(QtGui.QPen(color(self, "ink" if done or current else "hairline"), 1.2))
        p.setBrush(color(self, "inverse") if current else QtCore.Qt.NoBrush)
        p.drawEllipse(circle)
        p.setPen(color(self, "onInverse" if current else "ink" if done else "inkFaint"))
        p.setFont(role_font("mono", widget=self))
        p.drawText(self.rect(), QtCore.Qt.AlignCenter, "✓" if done else str(self.number))


class KeycapLarge(QtWidgets.QWidget):
    def __init__(self, text, parent=None, *, dark=False):
        super().__init__(parent)
        self.text, self.dark = text, dark
        self.setAccessibleName(text)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

    def sizeHint(self):
        return QtCore.QSize(scaled(88), scaled(88))

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        face = color(self, "inverse" if self.dark else "surface")
        bottom = color(self, "inkMuted" if self.dark else "sunk")
        p.setPen(QtGui.QPen(color(self, "hairline"), 1))
        p.setBrush(bottom)
        p.drawRoundedRect(rect, scaled(14), scaled(14))
        rect.adjust(0, 0, 0, -scaled(4))
        gradient = QtGui.QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0, face.lighter(110) if not high_contrast(self) else face)
        gradient.setColorAt(1, face)
        p.setBrush(gradient)
        p.drawRoundedRect(rect, scaled(14), scaled(14))
        p.setPen(color(self, "onInverse" if self.dark else "ink"))
        p.setFont(role_font("button", widget=self))
        p.drawText(rect.adjusted(scaled(12), scaled(10), -4, -4), QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, self.text)
        if self.text.casefold() == "win":
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(color(self,"onInverse" if self.dark else "ink"))
            for row in range(2):
                for column in range(2):
                    p.drawRect(QtCore.QRectF(rect.right()-scaled(32)+column*scaled(10),rect.bottom()-scaled(32)+row*scaled(10),scaled(8),scaled(8)))


class ShortcutIllustration(QtWidgets.QWidget):
    """Static drawing; never opens a capture port or starts a timer."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Illustration of the listening bar; no recording")
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)

    def sizeHint(self):
        return QtCore.QSize(scaled(244), scaled(40))

    def minimumSizeHint(self):
        return QtCore.QSize(100, scaled(40))

    def paintEvent(self, event):
        from .icons import svg_icon
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        scale = min(self.width()/244, self.height()/40)
        p.scale(scale, scale)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(bar_color(self, "bg"))
        p.drawRoundedRect(QtCore.QRectF(0, 0, 244, 40), 20, 20)
        p.setBrush(bar_color(self, "signal"))
        p.drawEllipse(QtCore.QRectF(6, 6, 28, 28))
        palette = QtGui.QPalette(self.palette())
        palette.setColor(QtGui.QPalette.WindowText, bar_color(self, "fg"))
        svg_icon("mic", palette, size=16, tone="palette").paint(p, 12, 12, 16, 16)
        p.setBrush(bar_color(self, "fg"))
        for i in range(22):
            height = (4, 8, 12, 16, 11, 6, 14)[i % 7]
            p.drawRoundedRect(QtCore.QRectF(44+i*4, (40-height)/2, 2, height), 1, 1)
        font = role_font("mono", widget=self)
        font.setPixelSize(11)
        p.setFont(font)
        p.setPen(bar_color(self, "fgMuted"))
        p.drawText(QtCore.QRectF(180, 0, 48, 40), QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight, "00:04")


class SetupRail(QtWidgets.QWidget):
    def __init__(self, wizard):
        super().__init__(wizard)
        self.setProperty("bare", True)
        self.setFixedWidth(264)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 28, 20, 24)
        root.setSpacing(12)
        root.addWidget(Label("SETUP · ABOUT 3 MINUTES", "label"))
        root.addSpacing(16)
        self.steps = []
        for number, name in enumerate(("Welcome", "Microphone", "Models", "Shortcut", "Try it", "Style"), 1):
            card = QtWidgets.QFrame()
            card.setProperty("bare", True)
            row = QtWidgets.QHBoxLayout(card)
            row.setContentsMargins(8, 6, 8, 6)
            row.setSpacing(12)
            marker = StepMarker(number)
            label = Label(name, "body")
            row.addWidget(marker)
            row.addWidget(label, 1)
            root.addWidget(card)
            self.steps.append((card, marker, label))
        root.addStretch(1)
        root.addWidget(Label("Nothing leaves this PC during setup, except the model download you start.", "caption"))
        self.counter = Label("STEP 1 OF 6", "label")
        root.addWidget(self.counter)

    def select(self, index):
        from .theme.style import repolish
        for i, (card, marker, label) in enumerate(self.steps):
            marker.state = "done" if i < index else "current" if i == index else "upcoming"
            marker.update()
            card.setProperty("card", i == index)
            label.setProperty("role", "body" if i <= index else "muted")
            repolish(card)
        self.counter.setText(f"STEP {index+1} OF 6")


def install_setup(wizard):
    wizard.setWindowTitle("Saydraft setup")
    wizard.setWizardStyle(QtWidgets.QWizard.ClassicStyle)
    wizard.resize(960, 680)
    wizard.setPixmap(QtWidgets.QWizard.BannerPixmap, QtGui.QPixmap())
    wizard.setPixmap(QtWidgets.QWizard.WatermarkPixmap, QtGui.QPixmap())
    wizard.rail = SetupRail(wizard)
    wizard.setSideWidget(wizard.rail)
    wizard.setButtonLayout([QtWidgets.QWizard.Stretch, QtWidgets.QWizard.BackButton,
                            QtWidgets.QWizard.CancelButton, QtWidgets.QWizard.CustomButton1,
                            QtWidgets.QWizard.NextButton, QtWidgets.QWizard.FinishButton])
    wizard.setButtonText(QtWidgets.QWizard.BackButton, "Back")
    wizard.setButtonText(QtWidgets.QWizard.CancelButton, "Cancel")
    wizard.setButtonText(QtWidgets.QWizard.FinishButton, "Finish setup")
    wizard.setButtonText(QtWidgets.QWizard.CustomButton1, "Skip")
    for button in (QtWidgets.QWizard.NextButton, QtWidgets.QWizard.FinishButton):
        wizard.button(button).setProperty("primary", True)
        repolish(wizard.button(button))
    for button in (QtWidgets.QWizard.BackButton, QtWidgets.QWizard.CancelButton):
        wizard.button(button).setProperty("ghost", True)
    # Skip follows the native Next route; it never bypasses a page's readiness.
    wizard.customButtonClicked.connect(lambda which: wizard.next() if which == QtWidgets.QWizard.CustomButton1 and wizard.currentId() == wizard.PAGE_PRACTICE and wizard.practice_page.isComplete() else None)
    def step(index):
        wizard.rail.select(max(0, index))
        buttons = [QtWidgets.QWizard.Stretch, QtWidgets.QWizard.BackButton, QtWidgets.QWizard.CancelButton]
        if index == wizard.PAGE_PRACTICE:
            buttons.append(QtWidgets.QWizard.CustomButton1)
        wizard.setButtonLayout(buttons + [QtWidgets.QWizard.NextButton, QtWidgets.QWizard.FinishButton])
        wizard.setButtonText(QtWidgets.QWizard.NextButton, "Get started" if index == 0 else "Next")
        wizard.setOption(QtWidgets.QWizard.HaveCustomButton1, index == wizard.PAGE_PRACTICE)
        wizard.button(QtWidgets.QWizard.CustomButton1).setEnabled(wizard.practice_page.isComplete())
    wizard.currentIdChanged.connect(step)
    wizard.practice_page.completeChanged.connect(lambda: step(wizard.currentId()))
    step(0)
    # Replace only the Welcome content; all other pages retain their logic.
    page = wizard.page(wizard.PAGE_WELCOME)
    page.setTitle("Your voice never leaves this PC.")
    layout = rebuild(page, margins=(24, 12, 24, 24), spacing=20)
    stage = Card(padding=28)
    stage.setProperty("setupStage", True)
    keys = QtWidgets.QHBoxLayout()
    keys.addStretch()
    keys.addWidget(KeycapLarge("Ctrl"))
    keys.addWidget(Label("+", "heading"))
    keys.addWidget(KeycapLarge("Win", dark=True))
    keys.addStretch()
    stage.body.addLayout(keys)
    stage.body.addSpacing(24)
    stage.body.addWidget(ShortcutIllustration(), alignment=QtCore.Qt.AlignCenter)
    stage.body.addSpacing(16)
    stage.body.addWidget(Label("Hold your shortcut. Speak. Release to insert.", "muted"))
    layout.addWidget(stage)
    layout.addWidget(Label("Voice typing that runs on your computer, with no account and no cloud.", "body"))
    layout.addWidget(control_row(Badge("No account"), Badge("No cloud"), Badge("Free and open source")))
    layout.addStretch(1)
    # Native combos remain the source of truth behind the new segments.
    style = wizard.style_page
    style.setTitle("Style")
    body = style.scroll.widget()
    old = body.layout()
    cards = QtWidgets.QWidget()
    row = AdaptiveRow(cards)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(16)
    style.card_previews = {}
    for group, caption, apps in (("messages", "Messages", "Chat and messaging apps"), ("email", "Email", "Mail and work correspondence")):
        card = Card(padding=20)
        card.body.setSpacing(12)
        card.body.addWidget(Label(caption, "subheading"))
        card.body.addWidget(Label(apps, "muted"))
        card.body.addWidget(Segmented(combo=style.tones[group], name=caption + " tone"))
        preview = Card(padding=16)
        preview.setProperty("field",True)
        label = style.card_previews[group] = Label("", "body")
        preview.body.addWidget(label)
        card.body.addWidget(preview)
        row.addWidget(card, 1)
    # The original form now contains only labels; its controls are in segments.
    import shiboken6
    for i in range(old.count()-1,-1,-1):
        form = old.itemAt(i).layout()
        if isinstance(form,QtWidgets.QFormLayout):
            while form.count():
                item = form.takeAt(0)
                if item.widget():
                    item.widget().hide()
            old.removeItem(form)
            shiboken6.delete(form)
    old.insertWidget(1, cards)
    style.refresh_preview()

    from .setup_content import arrange_model_step, arrange_shortcut_step, arrange_practice_step
    arrange_model_step(wizard.models_page)
    arrange_shortcut_step(wizard.shortcuts_page)
    arrange_practice_step(wizard.practice_page)
    for page_id in wizard.pageIds():
        page = wizard.page(page_id)
        page.setAttribute(QtCore.Qt.WA_StyledBackground)
        for scroll in page.findChildren(QtWidgets.QScrollArea):
            if scroll.widget() is not None:
                scroll.widget().setProperty("bare",True)
