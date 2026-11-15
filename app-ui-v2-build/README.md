# Desktop app UI reference

Open `index.html` locally for the searchable light/dark screenshot gallery.
This is a reference bundle, not another application or the website landing page.

- `source/saydraft/ui/`: current Qt widgets, layouts, components and themes.
- `source/saydraft/app.py.txt`: the app shell and UI/controller connections.
- `source/design/app-tokens.json`: desktop colors, typography and spacing tokens.
- `source/assets/fonts/`, `source/assets/icons/` and `source/assets/tray/`: actual assets and notices.
- `images/`: owned public-fixture captures, named by screen, theme and optional text size.
- `guides/`: setup, microphone, accessibility and Notes behavior to preserve.
- `manifest.json`: original paths and exact source hashes for every copied file.

Python files use `.py.txt` so this snapshot cannot shadow the functional app.
Use these files as redesign references; implement approved changes in the original
`saydraft/ui/` files. Refresh the bundle only into a new destination so edits here
are never overwritten. The export command is:

```powershell
python -m tools.export_app_ui_reference --output app-ui-new
```

Preserve recording/privacy consent, explicit model downloads, cancellation,
history-before-insertion and microphone test behavior while changing visuals.
Screenshots are public fixtures, not evidence of native owner-desktop acceptance.
