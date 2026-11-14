import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest

from saydraft.meetings.diarization import DiarizationCancelled, SpeakerDiarizer, SpeakerTurn
from saydraft.meetings.models import EMBEDDING_MODEL, SEGMENTATION_MODEL


class Native:
    sample_rate = 16000
    def __init__(self, turns=(), action=lambda: None):
        self.turns, self.action, self.calls = turns, action, []
    def process(self, waveform, callback):
        assert waveform.dtype == np.float32 and waveform.flags.c_contiguous
        self.calls.append(waveform.copy())
        callback(1, 2)
        self.action()
        callback(2, 2)
        return SimpleNamespace(sort_by_start_time=lambda: self.turns)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    models, directories = {}, {}
    for model_id, name in ((SEGMENTATION_MODEL, 'model.onnx'), (EMBEDDING_MODEL, 'embedding.onnx')):
        directory = tmp_path / model_id
        directory.mkdir()
        data = (model_id + ' fixture').encode()
        (directory / name).write_bytes(data)
        model = {'revision': 'frozen-test', 'files': [{'path': name, 'size': len(data),
                                                     'sha256': hashlib.sha256(data).hexdigest()}]}
        (directory / '.verified.json').write_text(json.dumps(model))
        models[model_id], directories[model_id] = model, directory
    monkeypatch.setattr('saydraft.meetings.diarization.get_model', models.__getitem__)
    native, calls = Native(), []
    def resolver(model_id, *, check_hashes):
        assert check_hashes is True
        return directories.get(model_id)
    def factory(*paths, **settings):
        calls.append((paths, settings))
        return native
    return SimpleNamespace(native=native, calls=calls, directories=directories,
                           create=lambda **kwargs: SpeakerDiarizer(resolver=resolver, factory=factory, **kwargs))


def turn(start, end, speaker):
    return SimpleNamespace(start=start, end=end, speaker=speaker)


def test_models_are_verified_once_before_native_load_and_never_downloaded(setup):
    diarizer = setup.create()
    assert not setup.calls
    diarizer.prepare()
    diarizer.prepare()
    assert len(setup.calls) == 1
    paths, settings = setup.calls[0]
    assert [path.name for path in paths] == ['model.onnx', 'embedding.onnx']
    assert settings == {'threads': 2, 'num_speakers': -1, 'threshold': .5}


@pytest.mark.parametrize('missing', [False, True])
def test_missing_or_tampered_artifact_never_reaches_native_constructor(setup, missing):
    directory = setup.directories[EMBEDDING_MODEL]
    if missing:
        del setup.directories[EMBEDDING_MODEL]
    else:
        (directory / 'embedding.onnx').write_bytes(b'corrupt')
    with pytest.raises(FileNotFoundError):
        setup.create().prepare()
    assert not setup.calls


def test_overlapping_turns_and_cluster_ids_are_preserved_with_bounded_end_rounding(setup):
    setup.native.turns = [turn(.8, 2.02, 1), turn(.2, 1.1, 0)]
    progress = []
    result = setup.create().diarize(np.zeros(32000, np.float64)[::-1], on_progress=progress.append)
    assert result == (SpeakerTurn(.2, 1.1, 0), SpeakerTurn(.8, 2., 1))
    assert progress == [.5, 1.]


@pytest.mark.parametrize('bad', [np.array([np.nan]), np.array([np.inf]), np.array([9.]),
    np.zeros((1, 10), np.float32), np.zeros(10, np.int16)])
def test_invalid_audio_is_rejected_before_model_loading(setup, bad):
    with pytest.raises(ValueError, match='audio'):
        setup.create().diarize(bad)
    assert not setup.calls


def test_empty_audio_does_not_load_models_or_create_speech(setup):
    assert setup.create().diarize(np.empty(0, np.float32)) == ()
    assert not setup.calls


@pytest.mark.parametrize('bad', [turn(-1., 1., 0), turn(0., float('nan'), 0), turn(1., .5, 0),
    turn(0., 2.2, 0), turn(2., 2.05, 0), turn(0., 1., -1), turn(0., 1., True), turn(0., 1., 32)])
def test_invalid_native_turns_are_refused_instead_of_silently_accepted(setup, bad):
    setup.native.turns = [bad]
    with pytest.raises(ValueError, match='turn'):
        setup.create().diarize(np.zeros(32000, np.float32))


def test_cancellation_before_load_and_after_native_return_never_publishes_partial_results(setup):
    with pytest.raises(DiarizationCancelled):
        setup.create().diarize(np.zeros(32000, np.float32), cancelled=lambda: True)
    assert not setup.calls
    cancelled = [False]
    setup.native.action = lambda: cancelled.__setitem__(0, True)
    with pytest.raises(DiarizationCancelled):
        setup.create().diarize(np.zeros(32000, np.float32), cancelled=lambda: cancelled[0])
    assert len(setup.native.calls) == 1


def test_progress_failure_waits_for_native_return_and_refuses_the_result(setup):
    def failed_progress(_value):
        raise RuntimeError('retired consumer')
    with pytest.raises(RuntimeError, match='consumer'):
        setup.create().diarize(np.zeros(32000, np.float32), on_progress=failed_progress)
    assert len(setup.native.calls) == 1


@pytest.mark.parametrize('settings', [{'threads': 0}, {'threads': True}, {'num_speakers': 0},
    {'num_speakers': 33}, {'threshold': float('nan')}, {'threshold': 1.1}])
def test_invalid_settings_are_rejected_without_native_initialization(settings):
    with pytest.raises(ValueError):
        SpeakerDiarizer(**settings)
