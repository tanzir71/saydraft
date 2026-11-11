from pathlib import Path
import os


def test_removed_stt_engines_are_not_referenced_in_runtime_sources():
    root = Path(__file__).resolve().parents[1]
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
                       and not (Path(directory) == root and name == "models")]
        for filename in files:
            path = Path(directory) / filename
            if path.suffix.lower() not in text_suffixes:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for term in forbidden_terms:
                if term in text:
                    hits.append(str(path.relative_to(root)))
                    break

    assert hits == []
