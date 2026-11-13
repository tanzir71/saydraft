"""Saved tier overrides and explicit, reviewable model defaults."""

TIERS = ("lite", "standard", "pro")


def effective_tier(config, report):
    selected = config.get("app", {}).get("tier", "auto")
    if selected in TIERS:
        return selected
    assessment = report.get("assessment") if isinstance(report, dict) else None
    measured = assessment.get("tier") if isinstance(assessment, dict) else None
    return measured if measured in TIERS else "pending"


def tier_defaults(tier, report=None):
    """Return choices only; the caller stages them before Save and explicit setup."""
    from saydraft.asr.model_ids import DEFAULT_MODEL
    from .manifest import load_manifest

    if tier not in TIERS:
        raise ValueError("Choose a tier or complete the performance check first")
    return {"asr_model": "whisper-base" if tier == "lite" else DEFAULT_MODEL,
            "cleanup_model": load_manifest()["cleanup_defaults"][tier],
            "backend": "vulkan" if tier != "lite" and (report or {}).get("vulkan") else "cpu"}
