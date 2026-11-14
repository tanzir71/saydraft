"""Public corpus acquisition retains reference provenance without full extraction."""

import hashlib
import io
import json
import random
import tarfile

import pytest

from tools.fetch_asr_corpus import FLEURS_CONFIGS, REVISION, fetch_language, parse_references


def archive(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as tar:
        for name, payload in entries:
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            tar.addfile(member, io.BytesIO(payload))
    return output.getvalue()


def row(identifier, name, text, *, normalized=None):
    return f'{identifier}\t{name}\t{text}\t{normalized or text}\tunused\t32000\tFEMALE\n'


def source(metadata, audio):
    calls = []
    def open_url(url):
        calls.append(url)
        assert REVISION in url
        return io.BytesIO(metadata if url.endswith('test.tsv') else audio)
    return calls, open_url


def test_source_locale_mapping_preserves_native_codes_and_brazil_scope():
    assert {code: FLEURS_CONFIGS[code] for code in ('pt', 'tl', 'zh', 'no', 'jw')} == {
        'pt': 'pt_br', 'tl': 'fil_ph', 'zh': 'cmn_hans_cn', 'no': 'nb_no', 'jw': 'jv_id'}
    assert {'th', 'ko', 'ja', 'hi', 'ur', 'id', 'ms', 'vi', 'ta', 'te', 'fa', 'fr', 'de', 'es'} <= FLEURS_CONFIGS.keys()


def test_independent_raw_and_normalized_references_retain_combining_marks():
    references = parse_references(row(10, '100.wav', 'Não, só um café.', normalized='não só um café').encode())
    assert references['100.wav']['reference'] == 'Não, só um café.'
    assert references['100.wav']['normalized_reference'] == 'não só um café'
    assert references['100.wav']['num_samples'] == 32000


@pytest.mark.parametrize('text', [
    '', 'bad\tcolumns\n', row(1, '../100.wav', 'Text'),
    row(1, '100.wav', 'Text') + row(2, '100.wav', 'Other'),
    row(1, '100.wav', ''),
])
def test_bad_or_ambiguous_reference_data_is_refused(text):
    with pytest.raises(ValueError):
        parse_references(text.encode())


def test_fetch_uses_archive_order_unique_ids_original_bytes_and_explicit_attribution(tmp_path):
    metadata = (row(7, '300.wav', 'สาม') + row(7, '301.wav', 'สาม') + row(8, '100.wav', 'หนึ่ง')).encode()
    payload = b'original source WAV bytes'
    calls, open_url = source(metadata, archive([
        ('../../outside.wav', b'bad'), ('test/300.wav', payload),
        ('test/301.wav', b'Another speaker, same utterance'), ('test/100.wav', b'second WAV'),
    ]))
    output = tmp_path / 'thai'
    receipt = fetch_language('th', output, samples=2, open_url=open_url)
    assert [clip['id'] for clip in receipt['clips']] == [7, 8]
    assert [clip['source_filename'] for clip in receipt['clips']] == ['300.wav', '100.wav']
    assert (output / 'audio/300.wav').read_bytes() == payload
    assert receipt['clips'][0]['sha256'] == hashlib.sha256(payload).hexdigest()
    assert receipt['metadata_sha256'] == hashlib.sha256(metadata).hexdigest()
    assert receipt['license'] == 'CC-BY-4.0' and receipt['revision'] == REVISION
    assert receipt['full_archive_checksum_verified'] is False
    assert receipt == json.loads((output / 'corpus.json').read_text(encoding='utf-8'))
    assert 'CC-BY-4.0' in (output / 'NOTICE.md').read_text(encoding='utf-8')
    assert len(calls) == 2 and not (tmp_path / 'outside.wav').exists()


def test_partial_or_size_limited_download_cannot_publish_complete_corpus(tmp_path):
    metadata = row(7, '300.wav', 'สาม').encode()
    _calls, open_url = source(metadata, archive([('300.wav', random.Random(0).randbytes(4096))]))
    output = tmp_path / 'limited'
    with pytest.raises(ValueError, match='size limit'):
        fetch_language('th', output, samples=1, max_transfer_bytes=1024, open_url=open_url)
    assert not (output / 'corpus.json').exists()
    assert (output / 'test.tsv').read_bytes() == metadata


def test_existing_output_is_preserved_before_any_network_access(tmp_path):
    original = tmp_path / 'owner.txt'
    original.write_text('retain me', encoding='utf-8')
    def forbidden(_url):
        raise AssertionError('No transfer for existing output')
    with pytest.raises(FileExistsError):
        fetch_language('th', tmp_path, samples=1, open_url=forbidden)
    assert original.read_text(encoding='utf-8') == 'retain me'
