from pathlib import Path
import os

import pytest


def legacy_runtime_hits(root):
    forbidden_terms = (
        "vo" "sk",
        "recognize_" "google",
        "speech_" "recognition",
        "speech" "recognition",
        "py" "audio",
    )
    text_suffixes = {".bat", ".ini", ".py", ".txt"}
    ignored_parts = {".git", ".pytest_cache", "__pycache__", ".venv", "venv", "build", "dist", "node_modules"}

    hits = []
    for directory, children, files in os.walk(root):
        children[:] = [name for name in children if name not in ignored_parts
                       and not (Path(directory) == root and name == "models")
                       # Retained reports, transcripts and source snapshots are
                       # evidence, never imported or packaged runtime sources.
                       and not (Path(directory).is_relative_to(root / "eval") and name == "results")]
        for filename in files:
            path = Path(directory) / filename
            if path.suffix.lower() not in text_suffixes:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for term in forbidden_terms:
                if term in text:
                    hits.append(str(path.relative_to(root)))
                    break

    return hits


def test_removed_stt_engines_are_not_referenced_in_runtime_sources():
    assert legacy_runtime_hits(Path(__file__).resolve().parents[1]) == []


@pytest.mark.parametrize("relative, expected", [
    ("saydraft/asr/engine.py", True),
    ("tools/recognize.py", True),
    ("requirements.txt", True),
    ("eval/asr/runner.py", True),
    ("saydraft/results/engine.py", True),
    ("eval/asr/results/old/source.py.txt", False),
])
def test_legacy_scan_preserves_runtime_coverage_and_archived_bytes(tmp_path, relative, expected):
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "import " + "py" "audio" + "\n"
    path.write_text(text, encoding="utf-8")
    assert legacy_runtime_hits(tmp_path) == ([str(Path(relative))] if expected else [])
    assert path.read_text(encoding="utf-8") == text
