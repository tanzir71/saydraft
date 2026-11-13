"""Read-only first-run recommendations; measured tier assessment stays separate."""

from saydraft.asr.model_ids import DEFAULT_MODEL


def setup_model_id(config):
    """Show the speech model the staged general context will actually load."""
    from saydraft.asr.selection import configured_model_id

    stt = config['stt']
    if not stt.get('routing_enabled', False):
        return configured_model_id(config)
    from saydraft.asr.router import choose_route

    overrides = {item['app_group']: item['model_id'] for item in stt.get('app_model_overrides', [])}
    return choose_route(stt.get('pinned_languages', []), english_max=stt.get('english_max', False),
        app_group='general', overrides=overrides).model_id


def capability_recommendation(report):
    report = report if isinstance(report, dict) else {}
    ram = report.get("ram_bytes")
    ram = ram if type(ram) is int and ram > 0 else None
    features = report.get("cpu_features")
    avx2 = features.get("avx2") if isinstance(features, dict) else None
    if (ram is not None and ram < 8 * 1024**3) or avx2 is False:
        tier, model = "lite", "whisper-base"
    elif ram is None or avx2 is not True:
        tier, model = "pending", DEFAULT_MODEL
    elif report.get("vulkan") or report.get("cuda"):
        tier, model = "pro", DEFAULT_MODEL
    else:
        tier, model = "standard", DEFAULT_MODEL
    return {"candidate_tier": tier, "speech_model": model, "provisional": True}


def inspect_speech_package(model_id, *, finder=None, local_resolver=None):
    """Verify every pinned dependency without creating folders or fetching files."""
    from saydraft.model_download import find_installed_model
    from .manifest import model_bundle

    # Injected catalog roots do not implicitly inspect the owner's HF cache.
    if finder is None and local_resolver is None:
        from .whisper_local import inspect_local
        local_resolver = inspect_local
    try:
        package = model_bundle(model_id)
    except ValueError:
        package = None
    finder = finder or find_installed_model
    missing = [model["label"] for model in package or [] if finder(model["id"], check_hashes=True) is None]
    if package is not None and not missing:
        return {"state": "verified", "missing": []}
    if model_id.startswith('whisper-') and local_resolver is not None:
        try:
            fingerprint = local_resolver(model_id.removeprefix('whisper-'))
            if (isinstance(fingerprint, str) and len(fingerprint) == 64
                    and all(c in '0123456789abcdef' for c in fingerprint)):
                return {'state': 'local', 'missing': [], 'fingerprint': fingerprint}
        except (OSError, ValueError):
            pass
    return {"state": "missing" if package is not None else "custom", "missing": missing}
