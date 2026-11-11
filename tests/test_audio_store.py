import numpy as np
import pytest

from saydraft.data.audio import AudioStore


def test_lossless_audio_is_published_atomically_and_can_be_read(tmp_path):
    store = AudioStore(tmp_path / "audio")
    assert not store.root.exists()
    samples = np.linspace(-0.3, 0.3, 16000, dtype=np.float32)
    path = store.save(samples)
    restored, rate = store.load(path)
    np.testing.assert_array_equal(restored, samples)
    assert rate == 16000 and path.suffix == ".wav"
    assert not list(store.root.glob("*.part"))


@pytest.mark.parametrize("value", ["outside.wav", "../outside.wav", r"\\example.invalid\share\speech.wav"])
def test_external_recording_paths_are_rejected_before_audio_io(tmp_path, monkeypatch, value):
    store = AudioStore(tmp_path / "audio")
    monkeypatch.setattr("saydraft.data.audio.sf.info", lambda path: pytest.fail("external audio was accessed"))
    with pytest.raises(ValueError, match="local audio history"):
        store.load(value)


def test_failed_write_keeps_partial_without_publishing_recording(tmp_path, monkeypatch):
    store = AudioStore(tmp_path / "audio")

    def failed(output, *args, **kwargs):
        output.write(b"partial retained audio")
        raise OSError("disk full")

    monkeypatch.setattr("saydraft.data.audio.sf.write", failed)
    with pytest.raises(OSError, match="disk full"):
        store.save(np.zeros(16000, dtype=np.float32))
    assert not list(store.root.glob("*.wav"))
    assert next(store.root.glob("*.part")).read_bytes() == b"partial retained audio"


def test_invalid_samples_and_stereo_are_rejected_without_creating_storage(tmp_path):
    store = AudioStore(tmp_path / "audio")
    for audio in (np.zeros((10, 2), dtype=np.float32), [float("nan")]):
        with pytest.raises(ValueError):
            store.save(audio)
    assert not store.root.exists()
