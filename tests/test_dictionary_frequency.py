import gzip
import hashlib
import json

import pytest

from saydraft.dictionary import frequency
from saydraft.privacy.netguard import NetworkGuard
from tools.build_frequency_lists import build


@pytest.fixture
def isolated_cache():
    frequency._load.cache_clear()
    frequency._manifest.cache_clear()
    yield
    frequency._load.cache_clear()
    frequency._manifest.cache_clear()


def test_every_bundled_language_has_verified_nonempty_common_words(isolated_cache):
    manifest = json.loads((frequency.ROOT / "manifest.json").read_bytes())
    assert len(manifest["languages"]) == 42
    assert {"en", "bn", "ar"} <= manifest["languages"].keys()
    for language, entry in manifest["languages"].items():
        words = frequency.common_words(language)
        assert words is not None and len(words) == entry["words"] > 1_000
        assert all(frequency.normalize_word(word) == word for word in words)
        raw = gzip.decompress((frequency.ROOT / f"{language}.txt.gz").read_bytes()).decode().splitlines()
        assert raw == sorted(words)
    for name, entry in manifest["notices"].items():
        data = (frequency.ROOT / name).read_bytes()
        assert len(data) == entry["bytes"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    assert frequency._load.cache_info().currsize == 4


@pytest.mark.parametrize("word,language", [
    ("the", "en"), ("THE", "en-US"), ("apple", "EN_gb"),
    ("আমি", "bn"), ("ভালো", "bn-BD"), ("বাংলা", "bn"),
    ("أنا", "ar"), ("مَرْحَبًا", "ar-SA"), ("بـخير", "ar"),
])
def test_ordinary_words_are_not_rare_even_with_lookup_variants(word, language):
    assert frequency.is_common(word, language) is True


def test_uncommon_terms_and_canonical_cache_aliases(isolated_cache):
    assert frequency.is_common("Kubernetes", "en") is False
    assert frequency.common_words("en-US") is frequency.common_words("EN_gb")
    assert frequency.common_words("no-NO") is frequency.common_words("nb")
    assert frequency.common_words("sr-Latn") is frequency.common_words("sh")
    assert frequency.common_words("tl") is frequency.common_words("fil")
    assert frequency._load.cache_info().currsize == 4
    # Bengali vowel marks remain distinct; normalization is for lookup only.
    assert frequency.normalize_word("ভালো") == "ভালো"
    assert frequency.normalize_word("L’Haÿ") == "l'haÿ"


@pytest.mark.offline
def test_uncached_language_loads_under_the_runtime_network_guard(isolated_cache):
    NetworkGuard.install()
    try:
        assert frequency.is_common("the", "en") is True
        assert frequency.is_common("আমি", "bn") is True
        assert frequency.is_common("مرحبا", "ar") is True
    finally:
        NetworkGuard.uninstall()


@pytest.mark.parametrize("language", ["auto", "xx", "../../en", "", None, "en/a", "en-" + "x" * 80])
def test_unknown_languages_and_invalid_identifiers_decline(language):
    assert frequency.is_common("unusualname", language) is None


def fake_bundle(tmp_path, monkeypatch, raw=b"ordinary\n", **overrides):
    packed = gzip.compress(raw, mtime=0)
    entry = {"bytes": len(packed), "sha256": hashlib.sha256(packed).hexdigest(), "words": 1}
    entry.update(overrides)
    (tmp_path / "en.txt.gz").write_bytes(packed)
    (tmp_path / "manifest.json").write_text(json.dumps({"format": 1, "languages": {"en": entry}}))
    monkeypatch.setattr(frequency, "ROOT", tmp_path)
    return tmp_path / "en.txt.gz"


@pytest.mark.parametrize("fault", ["missing", "hash", "size", "gzip", "encoding", "duplicate", "count", "empty", "truncated", "expanded", "compressed", "manifest"])
def test_unusable_data_declines_instead_of_learning_everything(tmp_path, monkeypatch, isolated_cache, fault):
    raw = {"encoding": b"\xff\n", "duplicate": b"a\na\n", "empty": b"\n", "truncated": b"ordinary"}.get(fault, b"ordinary\n")
    path = fake_bundle(tmp_path, monkeypatch, raw)
    if fault == "missing":
        path.unlink()
    elif fault in ("hash", "size", "gzip"):
        path.write_bytes(b"bad" if fault != "hash" else b"!" * path.stat().st_size)
        if fault == "gzip":
            fake_bundle(tmp_path, monkeypatch, raw)
            monkeypatch.setattr(frequency.gzip, "GzipFile", lambda **kw: (_ for _ in ()).throw(EOFError()))
    elif fault == "count":
        fake_bundle(tmp_path, monkeypatch, raw, words=2)
    elif fault == "expanded":
        monkeypatch.setattr(frequency, "MAX_EXPANDED", 2)
    elif fault == "compressed":
        monkeypatch.setattr(frequency, "MAX_COMPRESSED", 2)
    elif fault == "manifest":
        (tmp_path / "manifest.json").write_text("[]")
    assert frequency.is_common("newterm", "en") is None


def test_missing_manifest_declines(tmp_path, monkeypatch, isolated_cache):
    monkeypatch.setattr(frequency, "ROOT", tmp_path)
    assert frequency.is_common("newterm", "en") is None


def test_generator_rejects_unpinned_source_before_creating_output(tmp_path):
    wheel = tmp_path / "untrusted.whl"
    wheel.write_bytes(b"not a wheel")
    notice = tmp_path / "license.txt"
    notice.write_text("not the full license")
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="pinned wordfreq"):
        build(wheel, notice, output)
    assert not output.exists()
