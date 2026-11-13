"""Disposable model/cache metadata; no owner caches or network transfers."""

from types import SimpleNamespace
import os
from pathlib import Path

import pytest

from saydraft.models.setup import inspect_speech_package
from saydraft.models.whisper_local import cached_tokenizers, file_fingerprint, inspect_local, resolve_directory


@pytest.fixture
def local_model(tmp_path):
    root = tmp_path / 'public-local-model'
    root.mkdir()
    (root / 'model.bin').write_bytes(b'not native weights; metadata fixture only')
    (root / 'tokenizer.json').write_text('{}', encoding='utf-8')
    (root / 'config.json').write_text('{}', encoding='utf-8')
    return root


def test_cache_discovery_is_explicitly_local_only_and_creates_no_files(local_model, tmp_path):
    calls = []

    def lookup(name, **options):
        calls.append((name, options))
        return local_model

    before = set(tmp_path.rglob('*'))
    assert resolve_directory('base', finder=lambda *_a, **_k: None, cache_lookup=lookup) == local_model
    assert calls == [('base', {'local_files_only': True})] and set(tmp_path.rglob('*')) == before


def test_catalog_and_custom_directory_do_not_invoke_a_cache_lookup(local_model):
    def forbidden(*args, **kwargs):
        pytest.fail('An existing local directory must not consult a remote/cache name')

    assert resolve_directory('base', finder=lambda *_a, **_k: local_model, cache_lookup=forbidden) == local_model
    assert resolve_directory(str(local_model), finder=lambda *_a, **_k: None, cache_lookup=forbidden) == local_model


def test_unc_is_rejected_before_filesystem_or_cache_lookup():
    def forbidden(*args, **kwargs):
        pytest.fail('UNC paths must be rejected without lookup')

    with pytest.raises(FileNotFoundError):
        resolve_directory(r'\\remote.invalid\model', finder=forbidden, cache_lookup=forbidden)


def test_fingerprint_tracks_used_files_and_optional_metadata_but_not_owner_extras(local_model):
    original = file_fingerprint(local_model, tokenizers=())
    assert len(original) == 64
    (local_model / 'owner-notes.txt').write_text('public fixture notes', encoding='utf-8')
    assert file_fingerprint(local_model, tokenizers=()) == original
    (local_model / 'preprocessor_config.json').write_text('{}', encoding='utf-8')
    assert file_fingerprint(local_model, tokenizers=()) != original
    (local_model / 'model.bin').unlink()
    with pytest.raises(FileNotFoundError):
        file_fingerprint(local_model, tokenizers=())


def test_local_tokenizer_does_not_scan_an_unrelated_hf_cache(local_model, monkeypatch):
    monkeypatch.setattr('saydraft.models.whisper_local.cached_tokenizers', lambda: pytest.fail('unrelated cache lookup'))
    assert file_fingerprint(local_model)


def make_tokenizer(root, name='whisper-tiny'):
    repo = root / ('models--openai--' + name)
    (repo / 'refs').mkdir(parents=True)
    revision = 'a' * 40
    path = repo / 'snapshots' / revision / 'tokenizer.json'
    path.parent.mkdir(parents=True)
    path.write_text('{}', encoding='utf-8')
    (repo / 'refs' / 'main').write_text(revision, encoding='utf-8')
    return path


def test_cached_tokenizers_are_read_only_and_part_of_the_freshness_receipt(local_model, tmp_path):
    (local_model / 'tokenizer.json').unlink()
    cache = tmp_path / 'hf-cache'
    path = make_tokenizer(cache)
    before = set(tmp_path.rglob('*'))
    tokens = cached_tokenizers(root=cache)
    assert tokens == (path,)
    first = file_fingerprint(local_model, tokenizers=tokens)
    path.write_text('{"changed":true}', encoding='utf-8')
    assert file_fingerprint(local_model, tokenizers=cached_tokenizers(root=cache)) != first
    assert set(tmp_path.rglob('*')) == before
    path.unlink()
    with pytest.raises(FileNotFoundError):
        file_fingerprint(local_model, tokenizers=cached_tokenizers(root=cache))


@pytest.mark.parametrize('revision', ['../outside', 'a' * 40 + '\n', 'short', '\\remote.invalid\\model'])
def test_invalid_cache_refs_cannot_escape_the_cache_or_start_a_transfer(tmp_path, revision):
    path = make_tokenizer(tmp_path)
    (path.parents[2] / 'refs' / 'main').write_text(revision, encoding='utf-8')
    assert cached_tokenizers(root=tmp_path) == ()


def test_unpinned_cache_is_not_misrepresented_as_catalog_verified(local_model):
    fingerprint = file_fingerprint(local_model, tokenizers=())
    checked = []
    result = inspect_speech_package('whisper-base', finder=lambda *_a, **_k: None,
        local_resolver=lambda name: checked.append(name) or fingerprint)
    assert result == {'state': 'local', 'missing': [], 'fingerprint': fingerprint} and checked == ['base']
    assert inspect_speech_package('whisper-custom', finder=lambda *_a, **_k: None,
        local_resolver=lambda name: fingerprint)['state'] == 'local'


def test_missing_catalog_dependency_is_not_bypassed_by_a_whisper_cache(local_model):
    result = inspect_speech_package('parakeet-tdt-0-6b-v3-int8',
        finder=lambda name, **opts: None if 'lid' in name else local_model,
        local_resolver=lambda name: pytest.fail('A missing Parakeet dependency is required'))
    assert result['state'] == 'missing' and result['missing']


def test_default_loader_forces_offline_even_for_legacy_config_and_returns_freshness_receipt(local_model, monkeypatch):
    from saydraft.stt.whisper_engine import _default_model_factory

    calls = []
    monkeypatch.setattr('saydraft.models.whisper_local.resolve_directory', lambda name: local_model)
    monkeypatch.setattr('saydraft.stt.whisper_engine._import_whisper_model', lambda **opts:
        lambda *args, **kwargs: calls.append((args, kwargs)) or SimpleNamespace())
    model = _default_model_factory('base', local_files_only=False, device='cpu')
    assert calls == [((str(local_model),), {'local_files_only': True, 'device': 'cpu'})]
    assert model._saydraft_local_fingerprint == file_fingerprint(local_model, tokenizers=())


def test_missing_tokenizer_refuses_native_loading_instead_of_fetching(local_model, monkeypatch):
    from saydraft.stt.whisper_engine import _default_model_factory

    (local_model / 'tokenizer.json').unlink()
    monkeypatch.setattr('saydraft.models.whisper_local.resolve_directory', lambda name: local_model)
    monkeypatch.setattr('saydraft.models.whisper_local.cached_tokenizers', lambda: ())
    monkeypatch.setattr('saydraft.stt.whisper_engine._import_whisper_model', lambda **opts:
        lambda *args, **kwargs: pytest.fail('Missing tokenizer must be caught before native fallback'))
    with pytest.raises(FileNotFoundError):
        _default_model_factory('base')


def test_changed_files_during_native_loading_cannot_publish_a_receipt(local_model, monkeypatch):
    from saydraft.stt.whisper_engine import _default_model_factory

    def load(*args, **kwargs):
        (local_model / 'model.bin').write_bytes(b'changed public fixture')
        return SimpleNamespace()

    monkeypatch.setattr('saydraft.models.whisper_local.resolve_directory', lambda name: local_model)
    monkeypatch.setattr('saydraft.stt.whisper_engine._import_whisper_model', lambda **opts: load)
    with pytest.raises(FileNotFoundError, match='changed'):
        _default_model_factory('base')


def test_inspect_local_reuses_only_the_supplied_fixture_roots(local_model):
    assert inspect_local('base', finder=lambda *_a, **_k: local_model, tokenizers=()) == file_fingerprint(local_model, tokenizers=())


def test_loaded_receipt_detects_changed_files_and_a_new_alias_directory(local_model, tmp_path, monkeypatch):
    from saydraft.stt.whisper_engine import WhisperEngine

    selected = [local_model]
    monkeypatch.setattr('saydraft.models.whisper_local.resolve_directory', lambda *args, **kwargs: selected[0])
    engine = WhisperEngine()
    engine._model = SimpleNamespace(_saydraft_local_fingerprint=file_fingerprint(local_model, tokenizers=()),
        _saydraft_local_directory=local_model, _saydraft_model_name='base')
    assert engine.local_model_files_current() is True
    (local_model / 'model.bin').write_bytes(b'changed public weights')
    assert engine.local_model_files_current() is False
    engine._model._saydraft_local_fingerprint = file_fingerprint(local_model, tokenizers=())
    selected[0] = tmp_path / 'new-snapshot'
    selected[0].mkdir()
    assert engine.local_model_files_current() is False


def test_concurrent_metadata_and_runtime_imports_restore_socket_capability(monkeypatch):
    import builtins
    import socket
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    from saydraft.stt.whisper_engine import _import_whisper_model

    original_import = builtins.__import__
    entered, release, second_started = threading.Event(), threading.Event(), threading.Event()
    seen = []

    def importing(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'faster_whisper':
            seen.append(socket.has_ipv6)
            if len(seen) == 1:
                entered.set()
                assert release.wait(3)
            return SimpleNamespace(WhisperModel=object)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, '__import__', importing)
    monkeypatch.setattr(socket, 'has_ipv6', True)
    monkeypatch.setattr('saydraft.privacy.telemetry.disable_python_onnx_telemetry', lambda: None)
    monkeypatch.setattr('saydraft.privacy.telemetry.restrict_hub_to_cache', lambda: None)

    def second():
        second_started.set()
        return _import_whisper_model(suppress_ipv6_probe=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_import_whisper_model, suppress_ipv6_probe=True)
        try:
            assert entered.wait(1)
            other = pool.submit(second)
            assert second_started.wait(1)
            time.sleep(.02)
            assert seen == [False]
        finally:
            release.set()
        assert first.result(timeout=2) is object and other.result(timeout=2) is object
    assert seen == [False, False] and socket.has_ipv6 is True


def create_native_cache(tmp_path, monkeypatch):
    """Link only explicitly supplied public weights into a disposable HF snapshot."""
    directory = os.environ.get('SAYDRAFT_TEST_WHISPER_TURBO_MODEL')
    if not directory:
        pytest.skip('provide the explicit verified Whisper turbo fixture root for native cache checks')
    from saydraft.models.downloader import installation_ready
    from saydraft.models.manifest import get_model

    source = Path(directory)
    if source.drive != tmp_path.drive:
        pytest.skip('native cache fixtures need disposable storage on the model fixture volume')
    model = get_model('whisper-large-v3-turbo')
    assert installation_ready(model, source, check_hashes=True)
    root = tmp_path / 'model-cache'
    alias = 'public-fixture/whisper-turbo'
    repo = root / 'models--public-fixture--whisper-turbo'
    snapshot = repo / 'snapshots' / model['revision']
    snapshot.mkdir(parents=True)
    (repo / 'refs').mkdir()
    (repo / 'refs' / 'main').write_text(model['revision'], encoding='utf-8')
    for file in model['files']:
        os.link(source / file['path'], snapshot / file['path'])
    monkeypatch.setenv('HF_HOME', str(tmp_path / 'hf-home'))
    monkeypatch.setattr('huggingface_hub.constants.HF_HUB_CACHE', str(tmp_path / 'hf-home' / 'hub'))
    return SimpleNamespace(source=source, root=root, alias=alias, directory=snapshot, home=tmp_path / 'hf-home')


@pytest.fixture
def native_cache(tmp_path, monkeypatch):
    return create_native_cache(tmp_path, monkeypatch)


def bind_native_cache(monkeypatch, cache):
    from saydraft.models import whisper_local

    original = whisper_local.resolve_directory

    def lookup(name, **options):
        assert options == {'local_files_only': True}
        from saydraft.stt.whisper_engine import _import_whisper_model
        _import_whisper_model(suppress_ipv6_probe=True)
        from faster_whisper.utils import download_model
        return download_model(name, cache_dir=str(cache.root), **options)

    monkeypatch.setattr(whisper_local, 'resolve_directory', lambda name, **options:
        original(name, finder=lambda *_a, **_k: None, cache_lookup=lookup))


@pytest.mark.integration
@pytest.mark.offline
@pytest.mark.parametrize('tokenizer', ['model-local', 'cached', 'missing'])
def test_real_whisper_cache_and_tokenizer_fallback_are_offline(native_cache, monkeypatch, tokenizer):
    from saydraft.privacy.netguard import NetworkGuard
    from saydraft.asr.whisper_ct2 import WhisperCT2Engine, WhisperEngineConfig
    from huggingface_hub.errors import LocalEntryNotFoundError
    import requests

    def no_request(*args, **kwargs):
        raise AssertionError('No HTTP request is permitted for local or missing tokenizers')

    monkeypatch.setattr(requests.sessions.Session, 'request', no_request)
    monkeypatch.setattr('huggingface_hub.utils._headers.get_token', no_request)
    monkeypatch.setattr('huggingface_hub.constants.HF_HUB_OFFLINE', False)

    cache = native_cache
    bind_native_cache(monkeypatch, cache)
    if tokenizer != 'model-local':
        # Only remove the disposable link; preserve the verified source payload.
        (cache.directory / 'tokenizer.json').unlink()
        # The English-only cached entry cannot satisfy a multilingual model.
        name = 'whisper-tiny' if tokenizer == 'cached' else 'whisper-tiny.en'
        fallback = make_tokenizer(cache.home / 'hub', name)
        fallback.write_bytes((cache.source / 'tokenizer.json').read_bytes())
    NetworkGuard.install()
    engine = WhisperCT2Engine(WhisperEngineConfig(model_size=cache.alias, language='en', silence_trim=False))
    if tokenizer == 'missing':
        with pytest.raises(LocalEntryNotFoundError):
            engine.prepare()
        assert engine.local_model_fingerprint is None
    else:
        engine.prepare()
        assert engine.local_model_fingerprint == file_fingerprint(cache.directory)
        assert engine.local_model_files_current() is True
    assert (cache.source / 'tokenizer.json').is_file()
