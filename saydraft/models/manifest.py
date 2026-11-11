"""Read the bundled, revision-pinned model catalog without network requests."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit


def safe_filename(value):
    if (not isinstance(value, str) or value in ("", ".", "..") or value.endswith((" ", "."))
            or re.search(r'[/\\:<>"|?*\x00-\x1f]', value)
            or value.casefold() == ".verified.json"):
        return False
    return not re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", value.split(".", 1)[0], re.I)


def safe_member(value):
    if not isinstance(value, str):
        return False
    path = PurePosixPath(value)
    return (not path.is_absolute() and path.as_posix() == value and bool(path.parts)
            and all(safe_filename(part) for part in path.parts))


def validate_archive_model(model):
    """GitHub asset IDs and content hashes pin packages independently of mutable tags."""
    archive = model["archive"]
    if not isinstance(archive, dict):
        raise ValueError("Archive metadata must be an object")
    asset_id = archive.get("asset_id")
    url = urlsplit(archive.get("url", ""))
    if (type(asset_id) is not int or asset_id <= 0
            or model.get("revision") != f"github-release-asset-{asset_id}"
            or not model.get("license") or not isinstance(model.get("id"), str)
            or not re.fullmatch(r"[a-z0-9-]+", model["id"])
            or url.scheme != "https" or url.hostname != "api.github.com" or url.port not in (None, 443)
            or url.username or url.password or url.query or url.fragment
            or not re.fullmatch(rf"/repos/[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*/releases/assets/{asset_id}", url.path)
            or set(model.get("download_hosts", [])) != {"api.github.com", "release-assets.githubusercontent.com"}
            or archive.get("format") not in ("tar.bz2", "zip")
            or not safe_filename(archive.get("path"))
            or type(archive.get("size")) is not int or archive["size"] <= 0
            or not isinstance(archive.get("sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", archive["sha256"])):
        raise ValueError("Archive models require an immutable GitHub asset ID, HTTPS hosts, size and SHA-256")
    paths, members = set(), set()
    if (not isinstance(model.get("files"), list) or not model["files"]
            or any(not isinstance(file, dict) for file in model["files"])):
        raise ValueError("Archive models require declared payload files")
    for file in model["files"]:
        path = file.get("path")
        if (not safe_filename(path) or path.casefold() in paths
                or type(file.get("size")) is not int or file["size"] <= 0
                or not isinstance(file.get("sha256"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", file["sha256"])
                or ("member" in file) + ("bundled_source" in file) != 1):
            raise ValueError("Archive payloads require unique safe names, sizes and SHA-256")
        paths.add(path.casefold())
        if "member" in file:
            member = file["member"]
            if not safe_member(member) or member in members:
                raise ValueError("Archive member paths must be safe and unique")
            members.add(member)
        else:
            source = file["bundled_source"]
            if not safe_member(source) or not source.startswith("assets/licenses/"):
                raise ValueError("Bundled notices must stay inside assets/licenses")


def load_manifest(path: Path | None = None) -> dict:
    data = json.loads((path or Path(__file__).with_name("manifest.json")).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported model manifest schema")
    seen = set()
    for model in data["models"]:
        if model["id"] in seen or not re.fullmatch(r"[a-z0-9-]+", model["id"]):
            raise ValueError("model IDs must be unique safe directory names")
        seen.add(model["id"])
        if "archive" in model:
            validate_archive_model(model)
            continue
        if not model.get("license") or not re.fullmatch(r"[a-f0-9]{40}", model["revision"]):
            raise ValueError("models require an exact revision and license")
        paths = set()
        for file in model["files"]:
            url = urlsplit(file["url"])
            if (url.scheme != "https" or url.hostname not in model["download_hosts"]
                    or url.username or url.password or url.port not in (None, 443)
                    or f"/{model['revision']}/" not in url.path):
                raise ValueError("model URLs must be pinned HTTPS URLs on declared hosts")
            if (file["path"].casefold() in paths or not safe_filename(file["path"])
                    or not re.fullmatch(r"[a-f0-9]{64}", file["sha256"]) or file["size"] <= 0):
                raise ValueError("model files require unique safe names, sizes and SHA-256 checksums")
            paths.add(file["path"].casefold())
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
