"""Check the public documentation's local navigation, independent of marketing copy."""

from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("document", ["readme.md", "CONTRIBUTING.md", "docs/README.md"])
def test_public_documentation_local_links_resolve(document):
    source = ROOT / document
    destinations = re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", source.read_text(encoding="utf-8"))
    local_links = [urlsplit(link) for link in destinations if not urlsplit(link).scheme]

    assert local_links, f"No local documentation links checked in {document}"
    for link in local_links:
        destination = (source.parent / (unquote(link.path) or source.name)).resolve()
        assert destination.is_relative_to(ROOT), f"Link escapes repository: {link.path}"
        assert destination.is_file(), f"Broken link in {document}: {link.path}"
