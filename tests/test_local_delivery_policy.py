from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize('name', ['ci.yml', 'package.yml', 'site.yml', 'pages.yml', 'release.yml'])
def test_pushes_prs_tags_and_workflow_completions_never_start_actions(name):
    # BaseLoader preserves YAML's `on` key instead of interpreting it as YAML1.1
    # boolean True. These files remain valid manual tools without auto triggers.
    workflow = yaml.load((Path('.github/workflows') / name).read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
    assert set(workflow['on']) == {'workflow_dispatch'}


def test_optional_draft_release_requires_a_tag_and_never_waits_for_github_ci():
    path = Path('.github/workflows/release.yml')
    text = path.read_text(encoding='utf-8')
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert workflow['jobs']['unsigned-draft']['if'] == "startsWith(github.ref, 'refs/tags/v')"
    assert 'gh run list' not in text and '--draft --verify-tag' in text
