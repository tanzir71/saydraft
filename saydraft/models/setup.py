"""Read-only first-run recommendations; measured tier assessment stays separate."""

from saydraft.asr.model_ids import DEFAULT_MODEL


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


def inspect_speech_package(model_id, *, finder=None):
    """Verify every pinned dependency without creating folders or fetching files."""
    from saydraft.model_download import find_installed_model
    from .manifest import model_bundle

    try:
        package = model_bundle(model_id)
    except ValueError:
        return {"state": "custom", "missing": []}
    finder = finder or find_installed_model
    missing = [model["label"] for model in package if finder(model["id"], check_hashes=True) is None]
    return {"state": "missing" if missing else "verified", "missing": missing}
