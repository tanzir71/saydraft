"""Public audio -> installed-engine port -> rules -> independent references."""

import io
import json
import wave

import pytest

from tools import asr_accuracy as accuracy
from tools.fetch_asr_corpus import fetch_language
from tests.test_asr_corpus_fetch import archive, row, source


def corpus(tmp_path):
    audio = io.BytesIO()
    with wave.open(audio, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b'\0' * 64000)
    references = (row(1, '100.wav', 'Quero um livro.') + row(2, '200.wav', 'Quero um livro.')).encode()
    _calls, open_url = source(references, archive([('100.wav', audio.getvalue()), ('200.wav', audio.getvalue())]))
    root = tmp_path / 'public'
    fetch_language('pt', root, samples=2, open_url=open_url)
    return root / 'corpus.json'


def ports(monkeypatch, *, fail=False):
    engines = {}
    class Engine:
        last_language = 'pt'
        def __init__(self):
            self.prepares, self.languages = 0, []
        def prepare(self):
            self.prepares += 1
        def set_language(self, language):
            self.languages.append(language)
        def transcribe(self, _audio):
            if fail:
                raise RuntimeError('Scripted native failure')
            return 'Quero um livro.'
    def factory(model, _directory):
        engines[model] = Engine()
        return engines[model]
    monkeypatch.setattr(accuracy, '_engine', factory)
    monkeypatch.setattr(accuracy, '_source', lambda: {'commit': 'a' * 40, 'dirty': False, 'fingerprints': {'source': 'x'}})
    monkeypatch.setattr('saydraft.models.downloader.installation_ready', lambda *args, **kwargs: True)
    return engines


def test_portuguese_comparison_preserves_um_and_reuses_each_engine(tmp_path, monkeypatch):
    manifest = corpus(tmp_path)
    engines = ports(monkeypatch)
    report = accuracy.run([manifest], {accuracy.DEFAULT_MODEL: tmp_path, accuracy.ALL_LANGUAGES: tmp_path}, tmp_path / 'result')
    assert report['complete'] and report['measurement_integrity']
    assert report['expected_cases'] == report['completed_cases'] == 4
    assert len(engines) == 2
    for engine in engines.values():
        assert engine.prepares == 1 and engine.languages == ['pt', 'pt']
    cases = [json.loads(line) for line in (tmp_path / 'result/cases.jsonl').read_text(encoding='utf-8').splitlines()]
    assert all(case['asr_text'] == case['rules_text'] == 'Quero um livro.' for case in cases)
    for result in report['summary']['pt'].values():
        assert result['samples'] == 2 and result['cleanup_regressions'] == 0
        assert result['asr']['wer'] == result['rules']['cer'] == 0


def test_inference_failures_remain_in_denominators_and_do_not_certify_integrity(tmp_path, monkeypatch):
    manifest = corpus(tmp_path)
    ports(monkeypatch, fail=True)
    report = accuracy.run([manifest], {accuracy.DEFAULT_MODEL: tmp_path}, tmp_path / 'failure', recipe='routed')
    assert report['complete'] and not report['measurement_integrity']
    result = report['summary']['pt'][accuracy.DEFAULT_MODEL]
    assert result['samples'] == result['empty_outputs'] == result['inference_errors'] == 2
    assert result['asr']['reference_words'] == 6 and result['asr']['wer'] == 1
    assert result['rules']['cer'] == 1


@pytest.mark.parametrize('change', ['audio', 'reference', 'path', 'duplicate'])
def test_tampered_or_duplicate_corpus_is_refused_before_inference(tmp_path, change):
    manifest = corpus(tmp_path)
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if change == 'audio':
        (manifest.parent / data['clips'][0]['audio']).write_bytes(b'changed')
    elif change == 'reference':
        data['clips'][0]['reference'] = 'An invented reference.'
    elif change == 'path':
        data['clips'][0]['audio'] = '../private.wav'
    else:
        data['clips'].append(data['clips'][0])
    manifest.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        accuracy.load_corpora([manifest])


def test_routes_and_primary_metrics_match_language_boundaries():
    assert accuracy.models_for('pt', 'compare') == (accuracy.DEFAULT_MODEL, accuracy.ALL_LANGUAGES)
    assert accuracy.models_for('ja', 'routed') == (accuracy.ALL_LANGUAGES,)
    assert accuracy.models_for('de', 'routed') == (accuracy.DEFAULT_MODEL,)
    scores = accuracy.score('你好世界', '你好世')
    case = {'language': 'zh', 'model': accuracy.ALL_LANGUAGES, 'asr_text': '你好世',
            'audio_seconds': 2, 'asr_scores': scores, 'rules_scores': scores}
    result = accuracy.summarize([case])['zh'][accuracy.ALL_LANGUAGES]
    assert result['primary_metric'] == 'cer' and result['asr']['cer'] == 0.25


def test_quantity_surface_diagnostics_do_not_hide_signs_behind_normalized_zero_wer():
    assert accuracy.score('Pay -$25.', 'Pay $25.')['word_errors'] == 0
    assert accuracy.detail_surfaces('Pay -$25.') != accuracy.detail_surfaces('Pay $25.')
    assert accuracy.detail_surfaces('Pay €25.') != accuracy.detail_surfaces('Pay $25.')
