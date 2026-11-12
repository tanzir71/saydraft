"""Developer-only cleanup candidates; never part of the app's model picker."""

from __future__ import annotations

import re
from pathlib import Path

from saydraft.models.downloader import download_model, installation_ready, verify_file
from saydraft.models.manifest import load_manifest, safe_member

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG = ROOT / "eval" / "cleanup" / "candidates.json"


def _notice(model):
    notice = model.get("notice", {})
    relative = notice.get("path", "")
    if (not safe_member(relative) or not relative.startswith("assets/licenses/")
            or not relative.endswith(".txt") or type(notice.get("size")) is not int or notice["size"] <= 0
            or not re.fullmatch(r"[a-f0-9]{64}", notice.get("sha256", ""))):
        raise ValueError("Candidate requires a pinned bundled license notice")
    path = (ROOT / relative).resolve()
    if not path.is_relative_to((ROOT / "assets" / "licenses").resolve()):
        raise ValueError("Candidate notice escapes the bundled licenses")
    return path, notice


def load_candidates(path=DEFAULT_CATALOG):
    data = load_manifest(Path(path))
    if not data["models"]:
        raise ValueError("Candidate catalog is empty")
    for model in data["models"]:
        weights = [file for file in model["files"] if file["path"].endswith(".gguf")]
        if (model.get("role") != "cleanup_candidate" or model.get("status") != "unselected"
                or model.get("license") != "Apache-2.0" or model.get("engine") != "llama.cpp"
                or len(weights) != 1 or not re.fullmatch(r"[a-f0-9]{40}", model.get("source_revision", ""))):
            raise ValueError("Candidate must be unselected with one pinned GGUF and source revision")
        _notice(model)
    return data


def get_candidate(identifier, catalog=DEFAULT_CATALOG):
    for model in load_candidates(catalog)["models"]:
        if model["id"] == identifier:
            return model
    raise ValueError(f"No developer cleanup candidate: {identifier}")


def candidate_directory(root, model):
    return Path(root).resolve() / model["id"] / model["revision"]


def candidate_ready(model, directory):
    _, notice = _notice(model)
    return (installation_ready(model, Path(directory), check_hashes=True)
            and verify_file(Path(directory) / "LICENSE.txt", notice))


def candidate_weight(model, directory):
    if not candidate_ready(model, directory):
        raise ValueError("Candidate weights, card and license must be verified before evaluation")
    return Path(directory) / next(file["path"] for file in model["files"] if file["path"].endswith(".gguf"))


def download_candidate(identifier, root, *, catalog=DEFAULT_CATALOG, progress_callback=None, downloader=download_model):
    model = get_candidate(identifier, catalog)
    source, notice = _notice(model)
    if not verify_file(source, notice):
        raise ValueError("Bundled candidate license was changed or is unavailable")
    target = candidate_directory(root, model)
    license_path = target / "LICENSE.txt"
    if license_path.exists() and not verify_file(license_path, notice):
        raise ValueError("Retain the changed candidate license and choose a fresh directory")
    if candidate_ready(model, target):
        return target
    downloader(model, target, progress_callback=progress_callback)
    if not license_path.exists():
        with license_path.open("xb") as output:
            output.write(source.read_bytes())
    if not candidate_ready(model, target):
        raise ValueError("Candidate installation did not pass full verification")
    return target
