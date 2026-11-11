"""Read the bundled, revision-pinned model catalog without network requests."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def load_manifest(path: Path | None = None) -> dict:
    data = json.loads((path or Path(__file__).with_name("manifest.json")).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported model manifest schema")
    seen = set()
    for model in data["models"]:
        if model["id"] in seen or not re.fullmatch(r"[a-z0-9-]+", model["id"]):
            raise ValueError("model IDs must be unique safe directory names")
        seen.add(model["id"])
        if not model.get("license") or not re.fullmatch(r"[a-f0-9]{40}", model["revision"]):
            raise ValueError("models require an exact revision and license")
        paths = set()
        for file in model["files"]:
            url = urlsplit(file["url"])
            if (url.scheme != "https" or url.hostname not in model["download_hosts"]
                    or url.username or url.password or url.port not in (None, 443)
                    or f"/{model['revision']}/" not in url.path):
                raise ValueError("model URLs must be pinned HTTPS URLs on declared hosts")
            if (file["path"] in paths or Path(file["path"]).name != file["path"]
                    or file["path"] in ("", ".", "..") or "\\" in file["path"]
                    or not re.fullmatch(r"[a-f0-9]{64}", file["sha256"]) or file["size"] <= 0):
                raise ValueError("model files require unique safe names, sizes and SHA-256 checksums")
            paths.add(file["path"])
    return data


def get_model(model_id: str) -> dict:
    for model in load_manifest()["models"]:
        if model["id"] == model_id:
            return model
    raise ValueError(f"No pinned download is available for model {model_id}")
