"""Explicitly fetch a bounded, attributed public FLEURS corpus; never runs a model.

Audio stays outside the repository. Uses pinned TSVs and streams test archives,
avoiding the dataset viewer's current Parquet scan limit. Partial failures remain
in the manifest; they must not be counted as measured language accuracy.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import tarfile
import time
import urllib.request
from pathlib import Path, PurePosixPath

from saydraft.asr.languages import WHISPER_LANGUAGES

REVISION = '70bb2e84b976b7e960aa89f1c648e09c59f894dd'
SOURCE = 'https://huggingface.co/datasets/google/fleurs'
# Configuration identities from the pinned public dataset metadata. Do not infer
# regional decoder codes from country names: Brazilian Portuguese remains `pt`.
CONFIGS = '''af_za am_et ar_eg as_in az_az be_by bg_bg bn_in bs_ba ca_es cmn_hans_cn
cs_cz cy_gb da_dk de_de el_gr en_us es_419 et_ee fa_ir fi_fi fil_ph fr_fr gl_es gu_in
ha_ng he_il hi_in hr_hr hu_hu hy_am id_id is_is it_it ja_jp jv_id ka_ge kk_kz km_kh
kn_in ko_kr lb_lu ln_cd lo_la lt_lt lv_lv mi_nz mk_mk ml_in mn_mn mr_in ms_my mt_mt
my_mm nb_no ne_np nl_nl oc_fr pa_in pl_pl ps_af pt_br ro_ro ru_ru sd_in sk_sk sl_si
sn_zw so_so sr_rs sv_se sw_ke ta_in te_in tg_tj th_th tr_tr uk_ua ur_pk uz_uz vi_vn
yo_ng yue_hant_hk'''.split()
_ALIASES = {'cmn': 'zh', 'yue': 'yue', 'fil': 'tl', 'nb': 'no', 'jv': 'jw'}
FLEURS_CONFIGS = {_ALIASES.get(name.split('_')[0], name.split('_')[0]): name for name in CONFIGS}


class BoundedReader:
    def __init__(self, stream, limit, *, deadline):
        self.stream, self.limit, self.deadline = stream, limit, deadline
        self.bytes_read = 0

    def read(self, size=-1):
        if time.monotonic() >= self.deadline:
            raise TimeoutError('Public corpus transfer deadline exceeded')
        remaining = self.limit - self.bytes_read
        data = self.stream.read(min(size if size >= 0 else remaining + 1, remaining + 1))
        self.bytes_read += len(data)
        if self.bytes_read > self.limit:
            raise ValueError('Public corpus transfer size limit exceeded')
        return data


def parse_references(data):
    """FLEURS TSV: id, filename, raw, normalized, unused, samples, gender.

    Format verified against the upstream legacy loader at e8902c08388808c03401f633b045795dfca3bfa4.
    """
    result = {}
    for line in data.decode('utf-8').splitlines():
        fields = line.split('\t')
        if len(fields) != 7:
            raise ValueError('Unexpected public reference columns')
        identifier, name, raw, normalized, _unused, samples, gender = fields
        if (not identifier.isdecimal() or not re.fullmatch(r'[0-9]+\.wav', name)
                or name in result or not raw.strip() or not normalized.strip()
                or max(len(raw), len(normalized)) > 4096 or not samples.isdecimal()
                or gender not in ('MALE', 'FEMALE', 'OTHER')):
            raise ValueError('Invalid or duplicate public reference')
        result[name] = {'id': int(identifier), 'reference': raw, 'normalized_reference': normalized,
                        'num_samples': int(samples), 'gender': gender.lower()}
    if not result:
        raise ValueError('Public references are empty')
    return result


def _open(url):
    return urllib.request.urlopen(urllib.request.Request(url,
        headers={'User-Agent': 'Saydraft-public-evaluation/0.1'}), timeout=30)


def fetch_language(language, destination, *, samples=20, max_transfer_bytes=128 * 1024 * 1024,
                   open_url=_open):
    if language not in WHISPER_LANGUAGES or language not in FLEURS_CONFIGS:
        raise ValueError('No mapped FLEURS corpus for this language')
    if type(samples) is not int or not 1 <= samples <= 100:
        raise ValueError('Choose one to one hundred unique reference utterances')
    if type(max_transfer_bytes) is not int or not 1024 <= max_transfer_bytes <= 1024**3:
        raise ValueError('Invalid corpus transfer limit')
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('Choose a new public corpus directory')
    config = FLEURS_CONFIGS[language]
    prefix = f'{SOURCE}/resolve/{REVISION}/data/{config}'
    metadata_url, audio_url = f'{prefix}/test.tsv', f'{prefix}/audio/test.tar.gz'
    deadline = time.monotonic() + 600
    with open_url(metadata_url) as response:
        metadata = BoundedReader(response, 8 * 1024 * 1024, deadline=deadline).read()
    references = parse_references(metadata)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'test.tsv').write_bytes(metadata)
    audio_directory = destination / 'audio'
    audio_directory.mkdir()
    selected, identifiers = [], set()
    with open_url(audio_url) as response:
        compressed = BoundedReader(response, max_transfer_bytes, deadline=deadline)
        with gzip.GzipFile(fileobj=compressed, mode='rb') as unpacked:
            expanded = BoundedReader(unpacked, 512 * 1024 * 1024, deadline=deadline)
            with tarfile.open(fileobj=expanded, mode='r|') as archive:
                for member in archive:
                    path = PurePosixPath(member.name)
                    if path.is_absolute() or '..' in path.parts or not member.isfile():
                        continue
                    reference = references.get(path.name)
                    if (reference is None or reference['id'] in identifiers
                            or not 16000 <= reference['num_samples'] <= 60 * 16000):
                        continue
                    if not 1 <= member.size <= 4 * 1024 * 1024:
                        raise ValueError('Unexpected corpus audio member size')
                    audio = archive.extractfile(member)
                    if audio is None:
                        raise ValueError('Unreadable public audio member')
                    payload = audio.read(member.size + 1)
                    if len(payload) != member.size:
                        raise ValueError('Truncated public audio member')
                    target = audio_directory / path.name
                    with target.open('xb') as output:
                        output.write(payload)
                    selected.append({**reference, 'language': language, 'config': config, 'split': 'test',
                        'audio': f'audio/{path.name}', 'source_filename': path.name,
                        'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload)})
                    identifiers.add(reference['id'])
                    if len(selected) == samples:
                        break
    if len(selected) != samples:
        raise ValueError('Not enough eligible unique public utterances within transfer limits')
    receipt = {'schema': 1, 'dataset': 'google/fleurs', 'revision': REVISION,
        'license': 'CC-BY-4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'source': SOURCE, 'language': language, 'config': config, 'split': 'test',
        'metadata_url': metadata_url, 'metadata_sha256': hashlib.sha256(metadata).hexdigest(),
        'archive_url': audio_url, 'archive_bytes_read': compressed.bytes_read,
        'full_archive_checksum_verified': False,
        'selection': 'First eligible 1–60s regular WAV members in pinned archive order; unique utterance IDs; no inference used for selection.',
        'changes': 'Original audio bytes retained unchanged; placed in local audio folder.',
        'scope': 'small_public_read_speech_sample_not_owner_acceptance', 'complete': True, 'clips': selected}
    with (destination / 'corpus.json').open('x', encoding='utf-8') as output:
        json.dump(receipt, output, ensure_ascii=False, indent=2)
    (destination / 'NOTICE.md').write_text(
        '# Public FLEURS evaluation audio\n\n'
        f'By the Google FLEURS contributors. Source: {SOURCE}. Revision: `{REVISION}`.\n\n'
        'Licensed CC-BY-4.0: https://creativecommons.org/licenses/by/4.0/.\n'
        'Audio bytes are unchanged. Source filenames, references and hashes are in corpus.json.\n'
        'This data is separate from Saydraft’s MIT license.\n', encoding='utf-8')
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language', choices=sorted(FLEURS_CONFIGS), required=True)
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('Choose a new corpus directory; existing samples are retained')
    try:
        receipt = fetch_language(args.language, args.output, samples=args.samples)
    except (OSError, ValueError, tarfile.TarError, EOFError) as exc:
        print(json.dumps({'complete': False, 'language': args.language, 'error_type': type(exc).__name__}))
        return 1
    print(json.dumps({'complete': True, 'language': args.language, 'clips': len(receipt['clips']),
                      'archive_bytes_read': receipt['archive_bytes_read']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
