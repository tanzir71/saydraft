from pathlib import Path
import re


def test_manual_test_checklist_covers_required_targets():
    path = Path("docs/TEST_CHECKLIST.md")

    assert path.exists()
    text = path.read_text(encoding="utf-8").lower()
    for required in (
        "notepad",
        "vs code",
        "chrome textarea",
        "slack",
        "terminal fallback",
        "rdp focus-change",
    ):
        assert required in text


def test_manual_test_checklist_records_verification_commands():
    text = Path("docs/TEST_CHECKLIST.md").read_text(encoding="utf-8")
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    commands = re.findall(r"^\s*run: (python -m [^\r\n]+)$", workflow, re.MULTILINE)

    assert commands, "No CI verification commands found"
    for command in commands:
        assert command in text, f"Checklist is missing a CI gate: {command}"
