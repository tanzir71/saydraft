import hashlib
import json
import os
import sys
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from saydraft.asr.sherpa_stream import NemotronPreviewModel, _create_recognizer
from saydraft.core.preview import PreviewSession
from saydraft.privacy.netguard import NetworkGuard


def model_fixture(tmp_path, monkeypatch):
    content = b"verified fixture weights"
    (tmp_path / "weights").write_bytes(content)
    model = {"revision": "fixture", "files": [{"path": "weights", "size": len(content),
             "sha256": hashlib.sha256(content).hexdigest()}]}
    (tmp_path / ".verified.json").write_text(json.dumps(model), encoding="utf-8")
    monkeypatch.setattr("saydraft.asr.sherpa_stream.get_model", lambda model_id: model)
    streams, created = [], []

    class Stream:
        pending = False

        def __init__(self):
            self.audio = []
            self.text = ""

        def accept_waveform(self, rate, audio):
            assert rate == 16000
            self.audio.append(audio.copy())
            self.pending = True

        def input_finished(self):
            pass

    class Model:
        def create_stream(self):
            stream = Stream()
            streams.append(stream)
            return stream

        def is_ready(self, stream):
            return stream.pending

        def decode_stream(self, stream):
            stream.pending = False
            stream.text = f"stream {streams.index(stream)} words"

        def get_result(self, stream):
            return stream.text

    def factory(directory, threads):
        created.append((directory, threads))
        return Model()

    return NemotronPreviewModel(model_dir=tmp_path, factory=factory), streams, created


def test_weights_load_once_and_independent_streams_downmix_without_cross_cancellation(tmp_path, monkeypatch):
    model, streams, created = model_fixture(tmp_path, monkeypatch)
    first_updates, second_updates = [], []
    first, second = model.create_session(first_updates.append), model.create_session(second_updates.append)
    first.feed(np.tile([0.2, 0.4], (16000, 1)))
    np.testing.assert_allclose(streams[0].audio[0], 0.3)
    first.discard()
    second.feed(np.ones(16000))
    assert second.finish() == "stream 1 words" and second.complete
    assert len(created) == 1 and first_updates == ["stream 0 words"]
    assert second_updates == ["stream 1 words", "stream 1 words"]
    assert second.stream is None and second.callback is None


def test_tampered_weights_never_reach_native_factory(tmp_path, monkeypatch):
    model, _streams, created = model_fixture(tmp_path, monkeypatch)
    (tmp_path / "weights").write_bytes(b"modified fixture weights")
    with pytest.raises(FileNotFoundError, match="Download or resume"):
        model.create_session(lambda text: None)
    assert not created


def test_old_runtime_is_rejected_before_native_model_creation(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "sherpa_onnx", SimpleNamespace(__version__="1.13.3"))
    with pytest.raises(RuntimeError, match="1.13.4"):
        _create_recognizer(tmp_path, 4)


class FakeStream:
    complete = True
    compute_seconds = 0.1

    def __init__(self, callback, *, block=False):
        self.callback = callback
        self.started, self.release = threading.Event(), threading.Event()
        self.block = block
        self.audio, self.finished, self.discarded = [], 0, 0
        self.fail = False

    def feed(self, data):
        self.audio.append(data.copy())
        self.started.set()
        if self.block:
            assert self.release.wait(2)
        self.callback("available preview words")
        if self.fail:
            raise RuntimeError("decoder failure")

    def finish(self):
        self.finished += 1
        return "complete streaming words"

    def discard(self):
        self.discarded += 1


def queue_fixture(*, block=False, receiver=None):
    streams = []

    def create(callback):
        stream = FakeStream(callback, block=block)
        streams.append(stream)
        return stream

    failures, updates = [], []
    session = PreviewSession(SimpleNamespace(create_session=create), on_partial=receiver or updates.append,
        on_failed=lambda: failures.append(True))
    assert session.start()
    return session, streams[0], failures, updates


def test_capture_owns_queued_audio_and_finishes_without_repetition_filtering():
    session, stream, failures, updates = queue_fixture(block=True)
    assert session.feed(np.ones(1600)) and stream.started.wait(1)
    audio = np.full(1600, 0.2, dtype=np.float32)
    assert session.feed(audio)  # Waits behind the blocked first frame.
    audio[:] = 0
    stream.release.set()
    result = session.finish()
    np.testing.assert_allclose(stream.audio[1], 0.2)
    assert result.complete and not result.failed and not failures
    assert result.text == "complete streaming words" and updates == ["available preview words"] * 2
    assert stream.finished == stream.discarded == 1
    assert not session.feed(audio) and session.finish() is result


def test_overloaded_preview_stops_without_blocking_capture_or_publishing_late_results():
    session, stream, failures, updates = queue_fixture(block=True)
    assert session.feed(np.ones(1600)) and stream.started.wait(1)
    assert not session.feed(np.ones(32001))  # Exceeds the two-second queue cap.
    assert not session.feed(np.ones(1600))
    stream.release.set()
    result = session.finish()
    assert result.failed and not result.complete and failures == [True]
    assert result.failure_reason == "queue_overflow"
    assert updates == [] and stream.finished == 0
    assert result.text == "available preview words"  # Available for review, never complete output.


def test_discard_suppresses_late_updates_and_skips_native_flush():
    session, stream, failures, updates = queue_fixture(block=True)
    session.feed(np.ones(1600))
    assert stream.started.wait(1)
    session.request_finish(discard=True)
    stream.release.set()
    result = session.finish()
    assert result.text == "" and not result.complete and not result.failed
    assert not updates and not failures and stream.finished == 0


def test_decoder_failure_preserves_known_words_as_incomplete_result():
    session, stream, failures, _updates = queue_fixture(block=True)
    stream.fail = True
    session.feed(np.ones(1600))
    stream.release.set()
    result = session.finish()
    assert result.failed and not result.complete and result.text == "available preview words"
    assert failures == [True]


def test_missing_model_and_unavailable_ui_are_recoverable():
    failures = []

    def missing(callback):
        raise FileNotFoundError("model unavailable")

    session = PreviewSession(SimpleNamespace(create_session=missing), on_failed=lambda: failures.append(True))
    assert not session.start() and session.finish().failed and failures == [True]
    session, _stream, failures, _updates = queue_fixture(
        receiver=lambda text: (_ for _ in ()).throw(RuntimeError("UI closed")))
    session.feed(np.ones(1600))
    assert session.finish().complete and not failures


@pytest.mark.integration
@pytest.mark.offline
def test_native_preview_adapter_recognizes_fixture_when_enabled():
    directory = os.environ.get("SAYDRAFT_TEST_PREVIEW_MODEL")
    if not directory:
        pytest.skip("provide the explicit verified preview installation")
    import soundfile as sf

    NetworkGuard.install()
    try:
        model = NemotronPreviewModel(model_dir=directory)
        stream = model.create_session(lambda text: None)
        audio, rate = sf.read("tests/fixtures/hello.wav", dtype="float32")
        assert rate == 16000
        stream.feed(audio)
        assert "hello" in stream.finish().lower() and stream.complete
    finally:
        NetworkGuard.uninstall()
