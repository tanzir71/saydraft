"""Export a self-contained desktop UI reference without running the app."""

import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def export(output, extra_images=None, *, current_only=False):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / '.gitattributes').write_text('* -text -whitespace\n', encoding='utf-8')
    records, screenshots = [], []

    def copy(source, relative):
        assert source.is_file() and not source.is_symlink()
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest
        origin = source.relative_to(ROOT).as_posix() if source.is_relative_to(ROOT) else source.name
        records.append(dict(path=relative, original=origin, sha256=digest))

    paths = subprocess.check_output(['git', 'ls-files', '--', 'saydraft/ui', 'saydraft/app.py',
        'assets/fonts', 'assets/icons', 'assets/tray', 'design/app-tokens.json'], cwd=ROOT, text=True).splitlines()
    font_manifest=json.loads((ROOT/'assets/fonts/manifest.json').read_text(encoding='utf-8'))
    font_paths={'assets/fonts/manifest.json',*('assets/fonts/'+item['path'] for item in font_manifest['files'])}
    for name in paths:
        if current_only and name.startswith('assets/fonts/') and name not in font_paths:
            continue
        path = ROOT / name
        if path.is_file():
            # Reference snapshots must never become a second importable app.
            copy(path, 'source/' + name + ('.txt' if path.suffix == '.py' else ''))
    for name in ['MICROPHONE.md', 'ONBOARDING.md', 'HUB_ACCESSIBILITY.md', 'NOTES.md', 'APP_UI_V2.md', 'FONTS.md']:
        copy(ROOT / 'docs' / name, 'guides/' + name)
    folders = [] if current_only else [ROOT / 'eval/ui/results/2026-11-15-gallery/scale-1']
    if extra_images:
        folders.append(extra_images.resolve())
    for folder in folders:
        for path in sorted(folder.glob('*.png')):
            copy(path, 'images/' + path.name)
            screenshots.append(path.name)

    cards = '\n'.join(
        f'<figure data-name="{html.escape(name)}"><a href="images/{html.escape(name)}">'
        f'<img loading="lazy" src="images/{html.escape(name)}" alt="{html.escape(name.removesuffix(".png").replace("-", " "))}"></a>'
        f'<figcaption>{html.escape(name)}</figcaption></figure>' for name in screenshots)
    page = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Saydraft desktop app — UI reference</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f3ec;color:#1d2740;font:16px system-ui,sans-serif}
header{padding:40px clamp(20px,5vw,72px);max-width:1200px}h1{font-size:clamp(28px,4vw,46px);line-height:1.1}
p{line-height:1.6;max-width:80ch}a{color:inherit}input,select{font:inherit;padding:12px;border:1px solid #9298a3;border-radius:8px;max-width:100%}
nav{display:flex;gap:12px;flex-wrap:wrap}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));gap:24px;padding:0 clamp(20px,5vw,72px) 48px}
figure{margin:0;min-width:0;background:#fff;border:1px solid #d8d7d2;border-radius:12px;overflow:hidden}
figure img{display:block;width:100%;height:360px;object-fit:contain;padding:16px;background:#e9e7e2}figcaption{padding:16px;overflow-wrap:anywhere}
[hidden]{display:none!important}
</style><header><h1>Saydraft desktop app</h1>
<p>A dedicated reference for redesigning the Windows app. This folder includes widget source snapshots,
theme styles, shared tokens, fonts, tray assets and screenshots. The functional app stays in <code>saydraft/ui/</code>.
Read <a href="README.md">the source map and editing guide</a> before redesigning.</p>
<p>Most screenshots are retained QA gallery fixtures. Images beginning <code>current-</code> show the latest microphone fix.
They contain synthetic public examples. This gallery opens no microphone and runs no model.</p>
<nav><input id="search" type="search" aria-label="Filter screens" placeholder="Search screens, e.g. history or setup">
<select id="theme" aria-label="Filter theme"><option value="">Both themes</option><option value="light">Light</option><option value="dark">Dark</option></select></nav>
</header><main>''' + cards + '''</main><script>
const search=document.getElementById('search'),theme=document.getElementById('theme');
function filter(){for(const figure of document.querySelectorAll('figure')){const name=figure.dataset.name;
figure.hidden=!name.includes(search.value.toLowerCase().trim())||(theme.value&&!name.includes(theme.value));}}
search.addEventListener('input',filter);theme.addEventListener('change',filter);
</script></html>'''
    if current_only:
        page=page.replace('Saydraft desktop app','Saydraft desktop app UI v2').replace('Most screenshots are retained QA gallery fixtures. Images beginning <code>current-</code> show the latest microphone fix.',
            'These are current v2 production-widget captures with public fixtures. The native Windows caption is outside offscreen client captures.')
    (output / 'index.html').write_text(page, encoding='utf-8')
    (output / 'README.md').write_text('''# Desktop app UI reference

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
''', encoding='utf-8')
    manifest = dict(source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                    canonical_ui='saydraft/ui', screenshots=len(screenshots), records=records)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return dict(output=str(output), screenshots=len(screenshots), copied_files=len(records))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--extra-images', type=Path)
    parser.add_argument('--current-only',action='store_true',help='Export only supplied current images and manifest-listed fonts')
    args = parser.parse_args()
    print(json.dumps(export(args.output, args.extra_images,current_only=args.current_only)))


if __name__ == '__main__':
    main()
