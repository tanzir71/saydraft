"""Developer-only, bounded range retrieval of the authentic Parakeet tokenizer.

This never downloads weights or changes the app catalog. A pinned uncompressed
NeMo archive permits metadata seeks over weights. Its full checksum is NOT
verified by range retrieval; individual retained bytes and token-ID agreement
are recorded separately. Inference remains a separate explicit action.
"""

import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import struct
import tarfile
import time
import urllib.request

REVISION = '541d1f99c6b0c3cd0b11a95167540bb8edefd82b'
ARCHIVE_BYTES = 2509332480
ARCHIVE_SHA256 = '3cbdc85877e668ca7b82d0d56770eb1fac76691f55d6b97545e8d61ca588d10d'
URL = f'https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3/resolve/{REVISION}/parakeet-tdt-0.6b-v3.nemo'


class RangeReader(io.RawIOBase):
    def __init__(self, *, opener=urllib.request.urlopen, size=ARCHIVE_BYTES,
                 limit=8 * 1024**2, requests=64, seconds=180):
        self.opener, self.size, self.limit, self.requests = opener, size, limit, requests
        self.position = self.transferred = 0
        self.receipts = []
        self.deadline = time.monotonic() + seconds

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset if whence == 2 else -1
        if type(position) is not int or not 0 <= position <= self.size:
            raise ValueError('Range seek exceeds the pinned archive')
        self.position = position
        return position

    def read(self, size=-1):
        if type(size) is not int or not 0 <= size <= 1024**2:
            raise ValueError('Range reads must be explicitly bounded to 1 MiB')
        size = min(size, self.size - self.position)
        if not size:
            return b''
        if (self.transferred + size > self.limit or len(self.receipts) >= self.requests
                or time.monotonic() >= self.deadline):
            raise ValueError('Tokenizer transfer budget exceeded')
        first, last = self.position, self.position + size - 1
        request = urllib.request.Request(URL, headers={'Range': f'bytes={first}-{last}', 'Accept-Encoding': 'identity'})
        with self.opener(request, timeout=min(30, max(.01, self.deadline - time.monotonic()))) as response:
            if (response.status != 206 or response.headers.get('Content-Range') != f'bytes {first}-{last}/{self.size}'
                    or response.headers.get('Content-Encoding') not in (None, 'identity')):
                raise ValueError('Server did not honor the exact pinned archive range')
            payload = response.read(size + 1)
        if len(payload) != size or time.monotonic() > self.deadline:
            raise ValueError('Truncated, oversized or timed-out archive range')
        self.transferred += len(payload)
        self.position += len(payload)
        self.receipts.append({'first': first, 'last': last, 'bytes': size,
                              'sha256': hashlib.sha256(payload).hexdigest()})
        return payload


def _varint(data, position):
    value = 0
    for shift in range(0, 70, 7):
        if position >= len(data):
            break
        byte, position = data[position], position + 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, position
    raise ValueError('Invalid tokenizer protobuf varint')


def _fields(data):
    position = 0
    while position < len(data):
        tag, position = _varint(data, position)
        number, wire = tag >> 3, tag & 7
        if number < 1:
            raise ValueError('Invalid tokenizer protobuf field')
        if wire == 0:
            value, position = _varint(data, position)
        elif wire in (1, 2, 5):
            size, position = _varint(data, position) if wire == 2 else (8 if wire == 1 else 4, position)
            end = position + size
            if end > len(data):
                raise ValueError('Truncated tokenizer protobuf field')
            value, position = data[position:end], end
        else:
            raise ValueError('Unsupported tokenizer protobuf wire type')
        yield number, wire, value


def scored_pieces(payload, tokens):
    if not 1 <= len(payload) <= 1024**2 or not 1 <= len(tokens) <= 65536:
        raise ValueError('Invalid tokenizer size')
    result = []
    for number, wire, value in _fields(payload):
        if number != 1:
            continue
        if wire != 2 or len(result) >= 65536:
            raise ValueError('Invalid tokenizer piece message')
        fields = {}
        for key, kind, part in _fields(value):
            if key in fields:
                raise ValueError('Duplicate tokenizer piece field')
            fields[key] = (kind, part)
        if fields.get(1, (None,))[0] != 2 or fields.get(2, (None,))[0] != 5:
            raise ValueError('Missing authentic tokenizer text or score')
        piece = fields[1][1].decode('utf-8')
        score = struct.unpack('<f', fields[2][1])[0]
        if not piece or any(char.isspace() for char in piece) or not math.isfinite(score):
            raise ValueError('Invalid tokenizer piece or score')
        result.append((piece, score))
    expected = dict(tokens)
    # sherpa adds only its terminal blank to the original vocabulary.
    if expected.get(len(result)) == '<blk>':
        expected.pop(len(result))
    if (not result or len(expected) != len(result) or len({piece for piece, score in result}) != len(result)
            or any(expected.get(index) != piece for index, (piece, score) in enumerate(result))):
        raise ValueError('Tokenizer IDs do not match every pinned recognizer token')
    return result


def fetch(destination, tokens_file, *, reader=None, expected_tokens_sha256=None):
    destination, tokens_file = Path(destination), Path(tokens_file)
    if destination.exists():
        raise FileExistsError('Choose a new tokenizer evidence directory')
    with tokens_file.open('rb') as source:
        tokens_bytes = source.read(4 * 1024**2 + 1)
    if len(tokens_bytes) > 4 * 1024**2:
        raise ValueError('Token table exceeds size bound')
    if expected_tokens_sha256 is None:
        from saydraft.asr.model_ids import DEFAULT_MODEL
        from saydraft.models.manifest import get_model
        expected_tokens_sha256 = next(item['sha256'] for item in get_model(DEFAULT_MODEL)['files']
                                      if item['path'] == 'tokens.txt')
    if hashlib.sha256(tokens_bytes).hexdigest() != expected_tokens_sha256:
        raise ValueError('Recognizer tokens differ from the pinned catalog')
    tokens = {}
    for line in tokens_bytes.decode('utf-8').splitlines():
        piece, identifier = line.rsplit(' ', 1)
        identifier = int(identifier)
        if identifier in tokens:
            raise ValueError('Duplicate recognizer token ID')
        tokens[identifier] = piece
    reader = reader or RangeReader()
    candidates, members = [], []
    with tarfile.open(fileobj=reader, mode='r:') as archive:
        for member in archive:
            if len(members) >= 64:
                raise ValueError('Too many NeMo archive members')
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():
                raise ValueError('Unsupported NeMo archive path or link')
            members.append({'name': member.name, 'size': member.size, 'offset': member.offset_data})
            if path.name.endswith('tokenizer.model') and member.isfile():
                if not 1 <= member.size <= 1024**2:
                    raise ValueError('Unexpected tokenizer size')
                candidates.append(archive.extractfile(member).read(member.size + 1))
    if len(candidates) != 1:
        raise ValueError('Expected exactly one authentic tokenizer model')
    payload = candidates[0]
    pieces = scored_pieces(payload, tokens)
    vocab = ''.join(f'{piece}\t{score:.9g}\n' for piece, score in pieces).encode('utf-8')
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'tokenizer.model').write_bytes(payload)
    (destination / 'tokenizer.vocab').write_bytes(vocab)
    receipt = {'schema': 1, 'source': URL, 'revision': REVISION, 'archive_bytes': ARCHIVE_BYTES,
        'archive_sha256_from_publisher_metadata': ARCHIVE_SHA256, 'full_archive_checksum_verified': False,
        'license': 'CC-BY-4.0', 'source_model': 'nvidia/parakeet-tdt-0.6b-v3',
        'tokenizer_sha256': hashlib.sha256(payload).hexdigest(), 'vocab_sha256': hashlib.sha256(vocab).hexdigest(),
        'tokens_sha256': hashlib.sha256(tokens_bytes).hexdigest(), 'pieces': len(pieces),
        'all_token_ids_match': True, 'archive_members': members, 'ranges': reader.receipts,
        'changes': 'Tokenizer bytes unchanged; original float32 scores exported as round-trip decimal text',
        'transferred_bytes': reader.transferred, 'inference_performed': False,
        'scope': 'developer-only tokenizer capability investigation; no app model/catalog/default changes'}
    (destination / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    (destination / 'NOTICE.md').write_text(f'# Parakeet tokenizer investigation\n\nNVIDIA Parakeet TDT 0.6B v3, '
        f'revision {REVISION}, [source]({URL}). Weights/tokenizer: '
        '[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). '
        'Tokenizer bytes are retained unchanged; the vocabulary is an exported text representation '
        'of its original pieces and scores. Full archive checksum is not verified by partial ranges.\n', encoding='utf-8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tokens', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = fetch(args.output, args.tokens)
    print(json.dumps({key: result[key] for key in ('pieces', 'all_token_ids_match', 'transferred_bytes', 'inference_performed')}))


if __name__ == '__main__':
    main()
