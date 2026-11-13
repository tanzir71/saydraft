"""Two staged style choices and a rules preview before landing on Hub Home."""

import copy

from PySide6 import QtCore, QtWidgets

from saydraft.cleanup.styles import select_style
from saydraft.core.preferences import select_context
from saydraft.core.style_preview import MAX_PREVIEW, StylePreviewRequest, render_style_preview
from .private_text import PrivatePlainTextEdit


class OnboardingStylePage(QtWidgets.QWizardPage):
    def __init__(self, config, *, sample_provider=lambda group: '', ready_callback=lambda: True):
        super().__init__()
        self.setTitle('Style quick pick')
        self.config = copy.deepcopy(config)
        self.sample_provider = sample_provider
        self.ready_callback = ready_callback
        self.original, self.tones = {}, {}
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)

        def paragraph(text, name):
            label = QtWidgets.QLabel(text)
            label.setTextFormat(QtCore.Qt.PlainText)
            label.setWordWrap(True)
            label.setAccessibleName(name)
            policy = label.sizePolicy()
            policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Ignored)
            label.setSizePolicy(policy)
            layout.addWidget(label)
            return label

        paragraph('Choose a tone for Messages and Email. Finish saves your changed setup choices '
                  'and opens Home. You can adjust every app group later in Style.', 'Style setup guidance')
        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapAllRows)
        for group, label in (('messages', 'Messages'), ('email', 'Email')):
            tone = self.original[group] = select_style(config['dictation'], group).tone
            combo = self.tones[group] = QtWidgets.QComboBox()
            combo.setAccessibleName(f'{label} tone')
            combo.addItem('Casual', 'casual')
            combo.addItem('Formal', 'formal')
            if tone not in ('casual', 'formal'):
                combo.addItem('Keep current (very casual)', tone)
            combo.setCurrentIndex(combo.findData(tone))
            form.addRow(label, combo)
        layout.addLayout(form)
        self.group = QtWidgets.QComboBox()
        self.group.addItem('Messages preview', 'messages')
        self.group.addItem('Email preview', 'email')
        self.group.setAccessibleName('Style preview group')
        layout.addWidget(self.group)
        self.source_label = paragraph('', 'Style preview source')
        self.before = PrivatePlainTextEdit()
        self.before.setReadOnly(True)
        self.before.setAccessibleName('Style example before cleanup')
        self.before.setMinimumHeight(92)
        layout.addWidget(self.before)
        self.after = PrivatePlainTextEdit()
        self.after.setReadOnly(True)
        self.after.setAccessibleName('Style example after rules cleanup')
        self.after.setMinimumHeight(92)
        layout.addWidget(self.after)
        paragraph('Rules preview. AI cleanup settings and cleanup intensity stay unchanged; '
                  'tone changes also apply to optional local AI when it is enabled.', 'Style preview limits')
        self.status = paragraph('Finish to save your choices and open Home.', 'Setup completion status')
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setWidget(body)
        QtWidgets.QVBoxLayout(self).addWidget(self.scroll)
        for combo in self.tones.values():
            combo.currentIndexChanged.connect(self.refresh_preview)
        self.group.currentIndexChanged.connect(self.refresh_preview)
        self.refresh_preview()

    def merge_changes(self, latest):
        styles = copy.deepcopy(latest)
        for group, combo in self.tones.items():
            tone = combo.currentData()
            if tone != self.original[group]:
                fields = dict(styles.get(group, {}))
                fields['tone'] = tone
                styles[group] = fields
        return styles

    def isComplete(self):
        return bool(self.ready_callback())

    def refresh_preview(self):
        group = self.group.currentData()
        sample = self.sample_provider(group)
        self.source_label.setText('Your last practice transcript' if sample else 'Example text (not a recording)')
        sample = (sample or 'Um, could you send the draft by Friday? Thanks.')[:MAX_PREVIEW]
        config = copy.deepcopy(self.config)
        config['dictation']['styles'] = self.merge_changes(config['dictation'].get('styles', {}))
        context = select_context(config, [], 'Saydraft style setup', app_group=group)
        self.before.setPlainText(sample)
        result = render_style_preview(StylePreviewRequest(1, sample, context,
            drop_message_period=config['dictation'].get('drop_message_period', True)))
        self.after.setPlainText(result.text)

    def showEvent(self, event):
        if not self.isComplete():
            self.status.setText('Practice is stopping. Finish becomes available after its microphone and shortcuts retire.')
        self.refresh_preview()
        super().showEvent(event)
