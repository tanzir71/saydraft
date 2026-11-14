import hashlib
import io
import struct
import tarfile
from types import SimpleNamespace as NS

import pytest

from tools.fetch_parakeet_tokenizer import RangeReader, fetch, scored_pieces


def varint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    return bytes([*result, value])


def field(number, value):
    return varint(number * 8 + 2) + varint(len(value)) + value


def model(*pieces):
    return b''.join(field(1, field(1, piece.encode()) + b'\x15' + struct.pack('<f', score)) for piece, score in pieces)


def test_original_scores_and_all_ids_must_match_including_only_sherpas_terminal_blank():
    payload = model(('<unk>', 0.), ('▁Sintra', -17.25))
    assert scored_pieces(payload, {0:'<unk>', 1:'▁Sintra', 2:'<blk>'}) == [('<unk>', 0.), ('▁Sintra', -17.25)]
    for tokens in ({0:'<unk>', 1:'Sintra'}, {1:'<unk>', 0:'▁Sintra'}, {0:'<unk>', 1:'▁Sintra', 2:'other'}):
        with pytest.raises(ValueError, match='IDs'):
            scored_pieces(payload, tokens)


@pytest.mark.parametrize('payload', [b'', b'\x0a\xff', b'\x00', b'\x0b', b'\x80'*12,
    field(1, field(1,b'word')), model(('word', float('nan'))), model(('word', float('inf'))),
    model(('two words', 1.)), model(('same', 1.), ('same', 2.)),
    field(1, field(1,b'word')+field(1,b'other')+b'\x15'+struct.pack('<f',1.))])
def test_corrupt_ambiguous_or_nonfinite_tokenizer_is_rejected(payload):
    with pytest.raises((ValueError, UnicodeError)):
        scored_pieces(payload, {0:'word'})


class Response(io.BytesIO):
    status = 206
    def __init__(self, body, first, last, size):
        super().__init__(body)
        self.headers = {'Content-Range': f'bytes {first}-{last}/{size}'}


def reader_for(data, *, change=lambda response: response, **options):
    requests = []
    def open_url(request, **kwargs):
        first, last = map(int, request.get_header('Range').removeprefix('bytes=').split('-'))
        requests.append((first,last))
        return change(Response(data[first:last+1],first,last,len(data)))
    return RangeReader(opener=open_url, size=len(data), **options), requests


@pytest.mark.parametrize('fault', ['status', 'range', 'encoding', 'short', 'oversized'])
def test_unhonored_range_or_changed_body_fails_without_silently_downloading_weights(fault):
    def change(response):
        if fault=='status':
            response.status=200
        if fault=='range':
            response.headers['Content-Range']='bytes 1-3/6'
        if fault=='encoding':
            response.headers['Content-Encoding']='gzip'
        if fault=='short':
            response.truncate(1)
        if fault=='oversized':
            response.write(b'12345')
            response.seek(0)
        return response
    reader, requests = reader_for(b'abcdef',change=change)
    with pytest.raises(ValueError):
        reader.read(3)
    assert len(requests)==1 and reader.transferred==0


def test_range_budget_seek_and_unbounded_reads_fail_before_network():
    reader, requests = reader_for(b'abcdef',limit=3,requests=1)
    reader.seek(2)
    assert reader.read(3)==b'cde'
    for action in (lambda:reader.read(1),lambda:reader.read(),lambda:reader.seek(-1),lambda:reader.seek(7)):
        with pytest.raises(ValueError):
            action()
    assert len(requests)==1


def test_archive_seeks_over_large_weights_without_streaming_their_payload(tmp_path):
    payload = model(('<unk>',0.), ('▁Sintra',-17.25))
    weight_size = 2*1024**3
    weight = tarfile.TarInfo('model_weights.ckpt')
    weight.size=weight_size
    tokenizer=tarfile.TarInfo('prefix_tokenizer.model')
    tokenizer.size=len(payload)
    tokenizer_offset=512+weight_size
    tail=tokenizer.tobuf()+payload+b'\x00'*(-len(payload)%512)+b'\x00'*1024
    total=tokenizer_offset+len(tail)
    requests=[]
    def open_url(request,**options):
        first,last=map(int,request.get_header('Range').removeprefix('bytes=').split('-'))
        requests.append((first,last))
        body=b''.join(bytes([weight.tobuf()[index]]) if index<512 else
                      tail[index-tokenizer_offset:index-tokenizer_offset+1] if index>=tokenizer_offset else b'\x00'
                      for index in range(first,last+1))
        return Response(body,first,last,total)
    reader=RangeReader(opener=open_url,size=total)
    tokens=b'<unk> 0\n\xe2\x96\x81Sintra 1\n<blk> 2\n'
    path=tmp_path/'tokens.txt'
    path.write_bytes(tokens)
    result=fetch(tmp_path/'retained',path,reader=reader,expected_tokens_sha256=hashlib.sha256(tokens).hexdigest())
    assert result['all_token_ids_match'] and result['pieces']==2
    assert reader.transferred<4096 and any(first>weight_size for first,last in requests)
    assert not result['full_archive_checksum_verified'] and not result['inference_performed']
    assert (tmp_path/'retained/tokenizer.model').read_bytes()==payload


def test_changed_catalog_tokens_fail_before_any_archive_request(tmp_path):
    path=tmp_path/'tokens.txt'
    path.write_text('<unk> 0\n',encoding='utf-8')
    reader=NS(read=lambda *args:pytest.fail('Changed tokens must be rejected first'))
    with pytest.raises(ValueError,match='pinned catalog'):
        fetch(tmp_path/'output',path,reader=reader,expected_tokens_sha256='0'*64)
    assert not (tmp_path/'output').exists()
