import copy
import hashlib
import json

import pytest

from saydraft.cleanup.llm.candidates import (DEFAULT_CATALOG, ROOT, candidate_ready, candidate_weight,
    download_candidate, load_candidates)
from saydraft.models.downloader import verify_file
from saydraft.models.manifest import get_model


def test_developer_recipes_stay_pinned_and_only_measured_choices_enter_app_catalog():
    models = load_candidates()["models"]
    assert len(models) == 5
    assert {model["quantization"] for model in models} == {"Q4_K_M", "Q4_0"}
    for model in models:
        assert model["role"] == "cleanup_candidate" and model["status"] == "unselected"
        assert verify_file(ROOT / model["notice"]["path"], model["notice"])
        if model["id"] in ("qwen35-08b-q4-k-m", "qwen35-2b-q4-k-m"):
            selected = get_model(model["id"])
            assert selected["role"] == "llm" and selected["revision"] == model["revision"]
            assert selected["files"][:2] == model["files"]
        else:
            with pytest.raises(ValueError, match="No pinned download"):
                get_model(model["id"])


def fixture_catalog(tmp_path, mutate=lambda model: None):
    model = copy.deepcopy(load_candidates()["models"][0])
    payloads = {model["files"][0]["path"]: b"GGUF developer unit fixture", "README.md": b"licensed fixture"}
    for file in model["files"]:
        file.update(size=len(payloads[file["path"]]), sha256=hashlib.sha256(payloads[file["path"]]).hexdigest())
    mutate(model)
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"schema_version": 1, "models": [model]}), encoding="utf-8")
    calls = []
    def downloader(model, target, progress_callback=None):
        calls.append(target)
        target.mkdir(parents=True, exist_ok=True)
        for name, payload in payloads.items():
            (target / name).write_bytes(payload)
        (target / ".verified.json").write_text(json.dumps({"revision": model["revision"], "files": model["files"]}))
        if progress_callback:
            progress_callback(100)
    return model, catalog, downloader, calls


def test_explicit_transfer_copies_unchanged_license_and_reuses_a_fully_verified_cache(tmp_path):
    model, catalog, downloader, calls = fixture_catalog(tmp_path)
    progress = []
    target = download_candidate(model["id"], tmp_path / "models", catalog=catalog,
                                downloader=downloader, progress_callback=progress.append)
    assert target == (tmp_path / "models" / model["id"] / model["revision"]).resolve()
    assert candidate_ready(model, target) and candidate_weight(model, target).is_file()
    assert (target / "LICENSE.txt").read_bytes() == (ROOT / model["notice"]["path"]).read_bytes()
    assert progress == [100]
    assert download_candidate(model["id"], tmp_path / "models", catalog=catalog, downloader=downloader) == target
    assert calls == [target]
    candidate_weight(model, target).write_bytes(b"changed weight")
    assert not candidate_ready(model, target)
    with pytest.raises(ValueError, match="verified before evaluation"):
        candidate_weight(model, target)


def test_a_changed_installed_license_is_preserved_without_any_new_transfer(tmp_path):
    model, catalog, downloader, calls = fixture_catalog(tmp_path)
    target = download_candidate(model["id"], tmp_path / "models", catalog=catalog, downloader=downloader)
    license_path = target / "LICENSE.txt"
    license_path.write_bytes(b"retain owner edit")
    with pytest.raises(ValueError, match="Retain the changed"):
        download_candidate(model["id"], tmp_path / "models", catalog=catalog, downloader=downloader)
    assert license_path.read_bytes() == b"retain owner edit" and calls == [target]


@pytest.mark.parametrize("changes", [
    {"status": "selected"}, {"role": "asr"}, {"source_revision": "main"},
    {"notice": {"path": "../../settings.txt", "sha256": "a" * 64, "size": 1}},
    {"notice": {"path": "assets/licenses/no.txt", "sha256": "unverified", "size": 1}},
])
def test_unpinned_or_unsafe_metadata_is_rejected(tmp_path, changes):
    _, catalog, _, _ = fixture_catalog(tmp_path, lambda model: model.update(changes))
    with pytest.raises(ValueError):
        load_candidates(catalog)


def test_changed_bundled_license_is_rejected_before_creating_a_target_or_downloading(tmp_path):
    _, catalog, downloader, calls = fixture_catalog(tmp_path, lambda model: model["notice"].update(sha256="a" * 64))
    with pytest.raises(ValueError, match="Bundled candidate license"):
        download_candidate(load_candidates(catalog)["models"][0]["id"], tmp_path / "models",
                           catalog=catalog, downloader=downloader)
    assert not calls and not (tmp_path / "models").exists()


def test_cli_listing_has_no_transfer_and_download_requires_an_explicit_destination(capsys):
    from tools.download_cleanup_candidate import main

    assert main(["--list", "--catalog", str(DEFAULT_CATALOG)]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 5
    with pytest.raises(SystemExit) as error:
        main(["--candidate", "qwen35-08b-q4-k-m"])
    assert error.value.code == 2
