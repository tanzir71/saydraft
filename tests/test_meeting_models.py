import copy
import hashlib
import io
import json
import threading

import pytest

from saydraft.meetings.models import EMBEDDING_MODEL, SEGMENTATION_MODEL, download_speaker_models, speaker_bundle
from saydraft.models.downloader import DownloadPaused, download_model, installation_ready, verify_file
from saydraft.models.manifest import bundled_license_path, get_model, load_manifest
from saydraft.privacy.netguard import NetworkGuard


def test_speaker_bundle_is_separate_from_speech_models_and_retains_both_licenses():
    segmentation, embedding = speaker_bundle()
    assert [segmentation['id'], embedding['id']] == [SEGMENTATION_MODEL, EMBEDDING_MODEL]
    assert segmentation['license'] == 'MIT' and embedding['license'] == 'Apache-2.0'
    assert all(model['version'] == model['revision'] for model in speaker_bundle())
    assert all(model['role'].startswith('meeting_') and model['experimental'] for model in speaker_bundle())
    assert segmentation['files'][0]['sha256'] == '220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079'
    assert embedding['files'][0]['sha256'] == '1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b'
    for file in embedding['files'][1:]:
        assert verify_file(bundled_license_path(file['bundled_source']), file)


@pytest.mark.parametrize('mutation', [
    lambda m: m['asset'].update(id=True),
    lambda m: m['asset'].update(id=1),
    lambda m: m['asset'].update(repository='../outside'),
    lambda m: m['asset'].update(extra='ignored'),
    lambda m: m.update(download_hosts=['api.github.com', 'evil.example']),
    lambda m: m.update(revision='main'),
    lambda m: m['files'][0].update(url=m['files'][0]['url'] + '?unreviewed=1'),
    lambda m: m['files'][0].update(accept='application/json'),
    lambda m: m['files'].append(copy.deepcopy(m['files'][0])),
    lambda m: m.update(archive={}),
    lambda m: m['files'][0].update(path='../model.onnx'),
    lambda m: m['files'][0].update(sha256='unchecked'),
])
def test_raw_model_assets_refuse_mutable_ambiguous_or_unpinned_downloads(tmp_path, mutation):
    model = copy.deepcopy(get_model(EMBEDDING_MODEL))
    mutation(model)
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps({'schema_version': 1, 'models': [model]}))
    with pytest.raises(ValueError):
        load_manifest(path)


def test_raw_asset_uses_binary_accept_and_the_existing_size_hash_and_offline_cache_checks(tmp_path):
    content = b'controlled model fixture'
    model = copy.deepcopy(get_model(EMBEDDING_MODEL))
    model['files'] = [{**model['files'][0], 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()}]
    requests = []
    def opener(request, **kwargs):
        assert request.get_header('Accept') == 'application/octet-stream'
        assert request.full_url == model['files'][0]['url']
        requests.append(request)
        return io.BytesIO(content)
    prior = NetworkGuard.is_installed()
    try:
        download_model(model, tmp_path, opener=opener)
        assert installation_ready(model, tmp_path, check_hashes=True)
        download_model(model, tmp_path, opener=lambda *_a, **_k: pytest.fail('Verified cache must not request network'))
        assert len(requests) == 1
    finally:
        if not prior:
            NetworkGuard.uninstall()


def test_paused_setup_creates_no_installations_or_downloads(tmp_path):
    paused = threading.Event()
    paused.set()
    with pytest.raises(DownloadPaused):
        download_speaker_models(models_dir=tmp_path, pause_event=paused)
    assert not list(tmp_path.iterdir())
