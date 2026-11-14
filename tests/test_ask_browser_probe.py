"""Browser probe refuses owner sessions before loading Qt or native UIA."""

import json
import sys

import pytest

from tools.probe_ask_browser import answer_is_grounded, load_request


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


@pytest.mark.parametrize('kind', ['missing', 'file', 'evidence_root', 'outside', 'relative', 'non_string'])
def test_native_model_cache_must_be_an_existing_separate_owned_runner_directory(request_path, kind):
    root = request_path.parent.parent / 'native-models'
    if kind == 'file':
        root.write_text('Not a model directory')
    elif kind == 'evidence_root':
        root = request_path.parent
    elif kind == 'outside':
        root = request_path.parent.parent.parent
    elif kind == 'relative':
        root = 'relative-models'
    elif kind == 'non_string':
        root = False
    value = json.loads(request_path.read_text())
    value['models_dir'] = root if kind == 'non_string' else str(root)
    request_path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='model cache'):
        load_request(request_path)


def test_valid_native_request_selects_only_the_explicit_cache_and_does_not_load_a_model(request_path):
    root = request_path.parent.parent / 'native-models'
    root.mkdir()
    value = json.loads(request_path.read_text())
    value['models_dir'] = str(root)
    request_path.write_text(json.dumps(value))
    assert load_request(request_path) == value
    assert not list(root.iterdir())  # Request admission has no implicit setup or inference path.


@pytest.mark.parametrize('answer,expected', [
    ('The library opens on Saturday at 10:00.', True), ('Saturday at 10:00.', True),
    ('The library opens on Sunday at 10:00.', False), ('Saturday at 11:00.', False),
    ('It is closed on Saturday at 10:00.', False), ('It does not open on Saturday at 10:00.', False),
    (None, False), ('10:00.', False),
])
def test_authored_answer_anchors_reject_wrong_day_time_and_negation(answer, expected):
    assert answer_is_grounded(answer) is expected
