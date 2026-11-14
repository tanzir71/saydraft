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


def model_version(model):
    """The immutable source pin also names its version directory; old descriptors remain readable."""
    revision = model.get("revision")
    version = model.get("version", revision)
    if (not isinstance(version, str) or not safe_filename(version)
            or version.startswith((".", "_")) or len(version) > 160 or version != revision):
        raise ValueError("Model versions must match their immutable revision and be safe directory names")
    return version


def bundled_license_path(value):
    if not safe_member(value) or not value.startswith("assets/licenses/"):
        raise ValueError("Bundled notices must stay inside assets/licenses")
    root = Path(__file__).resolve().parents[2]
    path = (root / value).resolve()
    if not path.is_relative_to((root / "assets/licenses").resolve()):
        raise ValueError("Bundled notice escapes assets/licenses")
    return path


def validate_archive_model(model):
    """GitHub asset IDs and content hashes pin packages independently of mutable tags."""
    model_version(model)
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
        model_version(model)
        if "archive" in model:
            validate_archive_model(model)
            continue
        if not model.get("license") or not re.fullmatch(r"[a-f0-9]{40}", model["revision"]):
            raise ValueError("models require an exact revision and license")
        paths = set()
        for file in model["files"]:
            if "bundled_source" in file:
                bundled_license_path(file["bundled_source"])
                if "url" in file:
                    raise ValueError("Bundled notices cannot also have download URLs")
            else:
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
    for model in data["models"]:
        if "tasks" in model and (model.get("role") != "llm" or not isinstance(model["tasks"], list)
                or not model["tasks"] or any(task not in ("cleanup", "command", "translate") for task in model["tasks"])
                or len(set(model["tasks"])) != len(model["tasks"])):
            raise ValueError("LLM tasks must be unique supported task names")
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
    defaults = data.get("cleanup_defaults")
    if defaults is not None and (not isinstance(defaults, dict) or set(defaults) != {"lite", "standard", "pro"}
            or defaults["lite"] is not None or any(not isinstance(defaults[tier], str)
                or not supports_task(by_id.get(defaults[tier], {}), "cleanup") for tier in ("standard", "pro"))):
        raise ValueError("Cleanup defaults require rules-only Lite and catalogued Standard/Pro models")
    if "command_model" in data and (not isinstance(data["command_model"], str)
            or not supports_task(by_id.get(data["command_model"], {}), "command")):
        raise ValueError("Command Mode requires a catalogued command model")
    return data


def supports_task(model, task):
    """Legacy app LLM entries are cleanup choices; command selection is explicit."""
    return model.get("role") == "llm" and task in model.get("tasks", ["cleanup"])


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
