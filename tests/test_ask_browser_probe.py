"""Browser probe refuses owner sessions before loading Qt or native UIA."""

import json
import sys

import pytest

from tools.probe_ask_browser import load_request


@pytest.mark.parametrize('platform,actions,runner', [
    ('linux', 'true', 'github-hosted'), ('win32', None, None),
    ('win32', 'true', 'self-hosted'), ('win32', 'false', 'github-hosted'),
])
def test_browser_probe_refuses_every_non_disposable_environment_before_reading_request(monkeypatch, platform, actions, runner):
    monkeypatch.setattr(sys, 'platform', platform)
    monkeypatch.setenv('GITHUB_ACTIONS', actions or '')
    monkeypatch.setenv('RUNNER_ENVIRONMENT', runner or '')
    with pytest.raises(RuntimeError, match='owner desktop refused'):
        load_request('no-request-will-be-read.json')


@pytest.fixture
def request_path(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setenv('RUNNER_ENVIRONMENT', 'github-hosted')
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    root = tmp_path / 'fresh-browser-fixture'
    root.mkdir()
    path = root / 'request.json'
    path.write_text(json.dumps({'title': 'Saydraft read-only Ask public-id', 'browser_pid': 42,
                               'source': 'Public fixture.'}), encoding='utf-8')
    return path


@pytest.mark.parametrize('change', ['parent', 'filename', 'pid', 'title', 'extra'])
def test_request_must_match_owned_path_and_explicit_browser_identity(request_path, change):
    path = request_path
    if change == 'parent':
        path = path.parent / 'nested' / 'request.json'
        path.parent.mkdir()
        path.write_bytes(request_path.read_bytes())
    elif change == 'filename':
        path = path.with_name('unowned.json')
        path.write_bytes(request_path.read_bytes())
    else:
        value = json.loads(path.read_text())
        value.update({'pid': {'browser_pid': True}, 'title': {'title': 'Another browser'}, 'extra': {'extra': True}}[change])
        path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        load_request(path)


def test_valid_request_is_plain_metadata_without_loading_desktop_apis(request_path):
    assert load_request(request_path) == {'title': 'Saydraft read-only Ask public-id',
                                        'browser_pid': 42, 'source': 'Public fixture.'}
