"""Resolve existing Whisper files and track local changes without transferring data."""

import hashlib
import json
from pathlib import Path
import stat


FILES = ('model.bin', 'config.json', 'vocabulary.json', 'vocabulary.txt',
         'tokenizer.json', 'preprocessor_config.json')


def _local_path(value):
    if str(value).startswith(('\\\\', '//')):
        raise FileNotFoundError('Speech models must be available on local storage')
    return Path(value)


def resolve_directory(name, *, finder=None, cache_lookup=None):
    """Use the catalog, a custom directory, or a cache-only HF snapshot, in that order."""
    if finder is None:
        from saydraft.model_download import find_installed_model
        finder = find_installed_model
    _local_path(name)  # Reject UNC before any filesystem/cache operation.
    try:
        directory = finder('whisper-' + name, check_hashes=True)
    except ValueError:
        directory = None
    if directory is None and _local_path(name).is_dir():
        directory = name
    if directory is None:
        if cache_lookup is None:
            # This helper's local_files_only path never creates an installation.
            # Initialize telemetry/import policy before importing faster-whisper.
            from saydraft.stt.whisper_engine import _import_whisper_model
            _import_whisper_model(suppress_ipv6_probe=True)
            from faster_whisper.utils import download_model
            cache_lookup = download_model
        directory = cache_lookup(name, local_files_only=True)
    directory = _local_path(directory)
    if not directory.is_dir() or not (directory / 'model.bin').is_file():
        raise FileNotFoundError('Install or choose a complete local Whisper model')
    return directory


def cached_tokenizers(*, root=None):
    """Use the same cache root as tokenizers' Python HF download binding."""
    if root is None:
        from huggingface_hub.constants import HF_HUB_CACHE
        root = HF_HUB_CACHE
    root = _local_path(root)
    paths = []
    for name in ('whisper-tiny', 'whisper-tiny.en'):
        repo = root / ('models--openai--' + name)
        try:
            revision = (repo / 'refs' / 'main').read_text(encoding='utf-8')
            # Cache refs are untrusted paths. Accept exact immutable snapshots,
            # rather than letting a ref escape the cache directory.
            if len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
                continue
            path = repo / 'snapshots' / revision / 'tokenizer.json'
            if path.is_file():
                paths.append(path)
        except (OSError, UnicodeError):
            continue
    return tuple(paths)


def file_fingerprint(directory, *, tokenizers=None):
    """A freshness receipt, not a catalog checksum or a claim about model quality."""
    directory = _local_path(directory)
    local_tokenizer = directory / 'tokenizer.json'
    tokenizers = () if local_tokenizer.is_file() else tuple(cached_tokenizers() if tokenizers is None else tokenizers)
    if not local_tokenizer.is_file() and not tokenizers:
        raise FileNotFoundError('A local or cached Whisper tokenizer is required')
    paths = [directory / name for name in FILES]
    if not local_tokenizer.is_file():
        paths.extend(tokenizers)
    rows = []
    for path in paths:
        try:
            target = _local_path(path.resolve(strict=True))
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
                raise FileNotFoundError('Whisper files must be nonempty regular files')
            rows.append([str(path.absolute()), str(target), info.st_dev, info.st_ino,
                         info.st_size, info.st_mtime_ns, info.st_ctime_ns])
        except FileNotFoundError:
            if path.name == 'model.bin' or path == local_tokenizer and not tokenizers:
                raise
            rows.append([str(path.absolute()), None])
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode('utf-8')).hexdigest()


def inspect_local(name, *, finder=None, cache_lookup=None, tokenizers=None):
    directory = resolve_directory(name, finder=finder, cache_lookup=cache_lookup)
    return file_fingerprint(directory, tokenizers=tokenizers)
