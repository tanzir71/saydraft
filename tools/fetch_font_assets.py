"""Reproduce bundled font bytes in a NEW directory; never used by the app."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from saydraft.ui.fonts import ROOT, load_manifest, verify_font_assets


def fetch(output, *, root=ROOT):
    manifest = load_manifest(root)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for item in manifest["files"]:
        url = item.get("url", "")
        parts = urlsplit(url)
        expected = f"/google/fonts/{manifest['revision']}/ofl/"
        if parts.scheme != "https" or parts.netloc != "raw.githubusercontent.com" or not parts.path.startswith(expected):
            raise ValueError("Unexpected font source")
        with urlopen(url, timeout=30) as response:
            if response.geturl() != url:
                raise ValueError("Unexpected font redirect")
            content = response.read(item["size"] + 1)
        if len(content) != item["size"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError("Font source differs from pinned bytes")
        path = output / item["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    verify_font_assets(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    fetch(args.output)
    print("Verified all bundled font source bytes")


if __name__ == "__main__":
    main()
