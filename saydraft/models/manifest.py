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
    by_id = {model["id"]: model for model in data["models"]}
    checked = set()

    def check_dependencies(model_id, visiting):
        if model_id in visiting:
            raise ValueError("model dependencies must not contain cycles")
        if model_id in checked:
            return
        dependencies = by_id[model_id].get("requires", [])
        if not isinstance(dependencies, list) or any(
                not isinstance(value, str) or value not in by_id for value in dependencies):
            raise ValueError("model dependencies must name bundled catalog entries")
        for dependency in dependencies:
            check_dependencies(dependency, visiting | {model_id})
        checked.add(model_id)

    for model_id in by_id:
        check_dependencies(model_id, set())
    return data


def get_model(model_id: str) -> dict:
    for model in load_manifest()["models"]:
        if model["id"] == model_id:
            return model
    raise ValueError(f"No pinned download is available for model {model_id}")


def model_bundle(model_id: str) -> list[dict]:
    """One explicit setup action covers its displayed, licensed dependencies."""
    models = {model["id"]: model for model in load_manifest()["models"]}
    if model_id not in models:
        raise ValueError(f"No pinned download is available for model {model_id}")
    result = []
    seen = set()

    def visit(identifier):
        if identifier in seen:
            return
        seen.add(identifier)
        model = models[identifier]
        result.append(model)
        for dependency in model.get("requires", []):
            visit(dependency)

    visit(model_id)
    return result
