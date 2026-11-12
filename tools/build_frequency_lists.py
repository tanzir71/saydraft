"""Reproduce bundled word sets from a local pinned wheel; never download/install it."""

import argparse
import gzip
import hashlib
import json
import re
import zipfile
from pathlib import Path

import msgpack

from saydraft.dictionary.frequency import normalize_word

WHEEL_SHA256 = "4b1c6ecffc6198be3396d5cf871c4423ca71c907c231348d352dd54d62b97473"
WHEEL_BYTES = 56_834_549
WHEEL_URL = ("https://files.pythonhosted.org/packages/24/61/"
    "62835c475d69872d30689f284497853fe33fe1d6dd18f57346d13305861d/"
    "wordfreq-3.1.1-py3-none-any.whl")
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt"
LICENSE_SOURCE = ("https://raw.githubusercontent.com/creativecommons/cc-legal-tools-data/"
    "a0dac18d1a773b4cdb7d8dd5d9bf4efab7901030/docs/licenses/by-sa/4.0/legalcode.txt")
LICENSE_SHA256 = "28a9529c7d0bb4dc51f4bf5c116a3d16ef247a052f7591466768ddf563fd1cf5"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build(wheel: Path, license_path: Path, output: Path) -> dict:
    source = wheel.read_bytes()
    license_text = license_path.read_bytes()
    if len(source) != WHEEL_BYTES or digest(source) != WHEEL_SHA256:
        raise ValueError("Expected the pinned wordfreq 3.1.1 wheel")
    if digest(license_text) != LICENSE_SHA256:
        raise ValueError("Expected the pinned complete CC-BY-SA-4.0 text")
    # Never overwrite an existing directory, including a previous reproduction.
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"format": 1, "source": {"name": "wordfreq", "version": "3.1.1",
        "url": WHEEL_URL, "bytes": WHEEL_BYTES, "sha256": WHEEL_SHA256},
        "license": "CC-BY-SA-4.0", "attribution": "Copyright 2022 Robyn Speer",
        "changes": "Flatten small bins; normalize, omit empty/whitespace keys, deduplicate and sort; deterministic gzip.",
        "normalization": "NFKC, casefold, curly apostrophe to ASCII; omit Arabic tatweel and Arabic Mn marks",
        "languages": {}, "notices": {}}
    with zipfile.ZipFile(wheel) as archive:
        members = sorted(n for n in archive.namelist()
            if re.fullmatch(r"wordfreq/data/small_[a-z]{2,3}\.msgpack\.gz", n))
        if len(members) != 42:
            raise ValueError("Unexpected source language inventory")
        for member in members:
            bins = msgpack.unpackb(gzip.decompress(archive.read(member)), raw=False)
            if bins[0] != {"format": "cB", "version": 1}:
                raise ValueError("Unsupported frequency bin format")
            keys = {normalize_word(w) for group in bins[1:] for w in group}
            words = sorted(w for w in keys if w and not any(c.isspace() for c in w))
            packed = gzip.compress(("\n".join(words) + "\n").encode(), mtime=0)
            code = Path(member).name.removeprefix("small_").split(".")[0]
            (output / f"{code}.txt.gz").write_bytes(packed)
            manifest["languages"][code] = {"member": member, "words": len(words),
                "bytes": len(packed), "sha256": digest(packed), "omitted_keys": len(keys) - len(words)}
        metadata = archive.read("wordfreq-3.1.1.dist-info/METADATA").decode()
        notices = {
            "wordfreq-LICENSE.txt": archive.read("wordfreq-3.1.1.dist-info/LICENSE.txt"),
            "wordfreq-NOTICE.md": metadata[metadata.index("## License"):].encode(),
            "CC-BY-SA-4.0.txt": license_text,
        }
    for name, data in notices.items():
        (output / name).write_bytes(data)
        manifest["notices"][name] = {"sha256": digest(data), "bytes": len(data)}
    manifest["notices"]["CC-BY-SA-4.0.txt"]["url"] = LICENSE_URL
    manifest["notices"]["CC-BY-SA-4.0.txt"]["source"] = LICENSE_SOURCE
    (output / "manifest.json").write_bytes((json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode())
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--license", dest="license_path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.wheel, args.license_path, args.output)
    print(f"Built {len(result['languages'])} offline word sets in {args.output}")


if __name__ == "__main__":
    main()
