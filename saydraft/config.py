"""JSON configuration with migration from legacy ``settings.txt``."""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_VERSION = 1

CONFIG_SCHEMA: dict[str, Any] = {
    "schema_version": int,
    "hotkeys": {
        "speech": str,
        "speech_alternative": str,
        "speech_mouse": str,
        "hands_free": str,
        "paste_last": str,
        "save": str,
        "cancel": str,
        "tap_lock_ms": int,
    },
    "app": {
        "start_with_windows": bool,
        "auto_start_listening": bool,
        "show_bar": bool,
        "notification_duration": int,
        "onboarded": bool,
    },
    "labs": {"live_preview": bool, "use_streaming_result": bool},
    "recording": {
        "retain_audio": bool,
        "max_seconds": int,
        "warning_seconds": int,
    },
    "dictation": {
        "mode": str,
        "profile": str,
        "glossary_path": str,
        "app_profiles_path": str,
        "drop_message_period": bool,
        "voice_enter_enabled": bool,
        "learn_corrections": bool,
        "auto_add_dictionary": bool,
        "styles": dict,
    },
    "stt": {
        "routing_enabled": bool,
        "pinned_languages": list,
        "english_max": bool,
        "fallback_budget_ms": int,
        "app_model_overrides": list,
        "engine": str,
        "model_id": str,
        "model_size": str,
        "language": str,
        "device": str,
        "compute_type": str,
        "local_files_only": bool,
        "background_transcription": bool,
        "silence_trim": bool,
        "silence_padding_ms": int,
        "vad_aggressiveness": int,
        "vad_energy_threshold": float,
    },
    "llm": {
        "enabled": bool,
        "model_path": str,
        "n_ctx": int,
        "max_tokens": int,
        "temperature": float,
        "top_p": float,
        "threads": (int, type(None)),
        "gpu_layers": (int, type(None)),
        "backend": str,
        "timeout_ms": int,
        "idle_seconds": int,
    },
}

_DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": DEFAULT_CONFIG_VERSION,
    "hotkeys": {
        "speech": "ctrl+win",
        "speech_alternative": "f9",
        "speech_mouse": "xbutton1",
        "hands_free": "ctrl+win+space",
        "paste_last": "shift+alt+z",
        "save": "f10",
        "cancel": "esc",
        "tap_lock_ms": 300,
    },
    "app": {
        "start_with_windows": False,
        "auto_start_listening": True,
        "show_bar": True,
        "notification_duration": 3,
        "onboarded": False,
    },
    "labs": {"live_preview": False, "use_streaming_result": False},
    "recording": {
        "retain_audio": False,
        "max_seconds": 1200,
        "warning_seconds": 1140,
    },
    "dictation": {
        "mode": "balanced",
        "profile": "general",
        "glossary_path": "glossary.json",
        "app_profiles_path": "app_profiles.json",
        "drop_message_period": True,
        "voice_enter_enabled": False,
        "learn_corrections": False,
        "auto_add_dictionary": False,
        "styles": {},
    },
    "stt": {
        "routing_enabled": True,
        "pinned_languages": [],
        "english_max": False,
        "fallback_budget_ms": 800,
        "app_model_overrides": [],
        "engine": "parakeet",
        "model_id": "parakeet-tdt-0-6b-v3-int8",
        "model_size": "base",
        "language": "auto",
        "device": "cpu",
        "compute_type": "int8",
        "local_files_only": True,
        "background_transcription": True,
        "silence_trim": True,
        "silence_padding_ms": 120,
        "vad_aggressiveness": 2,
        "vad_energy_threshold": 0.003,
    },
    "llm": {
        "enabled": False,
        "model_path": "models/llm/model.gguf",
        "n_ctx": 4096,
        "max_tokens": 256,
        "temperature": 0.05,
        "top_p": 0.9,
        "threads": None,
        "gpu_layers": None,
        "backend": "cpu",
        "timeout_ms": 800,
        "idle_seconds": 900,
    },
}

_LEGACY_KEY_MAP: dict[str, tuple[str, ...]] = {
    "speech_hotkey": ("hotkeys", "speech"),
    "save_hotkey": ("hotkeys", "save"),
    "start_with_windows": ("app", "start_with_windows"),
    "auto_start_listening": ("app", "auto_start_listening"),
    "notification_duration": ("app", "notification_duration"),
    "dictation_mode": ("dictation", "mode"),
    "format_profile": ("dictation", "profile"),
    "glossary_path": ("dictation", "glossary_path"),
    "app_profiles_path": ("dictation", "app_profiles_path"),
    "llm_enabled": ("llm", "enabled"),
    "llm_model_path": ("llm", "model_path"),
    "llm_n_ctx": ("llm", "n_ctx"),
    "llm_max_tokens": ("llm", "max_tokens"),
    "llm_temperature": ("llm", "temperature"),
    "llm_top_p": ("llm", "top_p"),
    "llm_threads": ("llm", "threads"),
    "llm_gpu_layers": ("llm", "gpu_layers"),
}


def default_config() -> dict[str, Any]:
    """Return a mutable copy of the built-in defaults."""

    return copy.deepcopy(_DEFAULT_CONFIG)


def default_config_path(local_appdata: str | os.PathLike[str] | None = None) -> Path:
    base = Path(local_appdata) if local_appdata is not None else _default_local_appdata()
    return base / "Saydraft" / "config.json"


def default_settings_path() -> Path:
    return Path(__file__).resolve().parents[1] / "settings.txt"


def load_config(
    *,
    config_path: str | os.PathLike[str] | None = None,
    settings_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Load, migrate, sanitize, and persist Saydraft configuration."""

    target = Path(config_path) if config_path is not None else default_config_path()
    legacy_settings = (
        Path(settings_path) if settings_path is not None else default_settings_path()
    )

    if target.exists():
        cfg = _read_json_config(target)
    else:
        cfg = default_config()
        if legacy_settings.exists():
            cfg = migrate_settings_txt(legacy_settings)

    cfg = sanitize_config(cfg)
    save_config(cfg, target)
    return cfg


def save_config(
    config: dict[str, Any],
    config_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Sanitize and write config JSON, returning the saved config."""

    target = Path(config_path) if config_path is not None else default_config_path()
    cfg = sanitize_config(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return cfg


def sanitize_config(config: dict[str, Any] | None) -> dict[str, Any]:
    source = config if isinstance(config, dict) else {}
    defaults = default_config()
    hotkeys = source.get("hotkeys", {})
    if not isinstance(hotkeys, dict) or "speech_mouse" not in hotkeys:
        # Old profiles keep their key order and never acquire mouse interception.
        defaults["hotkeys"].update(speech="f9", speech_alternative="ctrl+win", speech_mouse="")
    cfg = _sanitize_mapping(source, CONFIG_SCHEMA, defaults)
    from .cleanup.styles import sanitize_styles
    cfg["dictation"]["styles"] = sanitize_styles(cfg["dictation"]["styles"])
    # Existing JSON predates engine selection. Keep its Whisper model preference.
    stt = source.get("stt", {})
    if not isinstance(stt, dict) or stt.get("engine") not in ("whisper", "parakeet"):
        cfg["stt"]["engine"] = "whisper"
    if not isinstance(stt, dict) or type(stt.get("routing_enabled")) is not bool:
        cfg["stt"]["routing_enabled"] = False
    if cfg["stt"]["model_id"] not in ("parakeet-tdt-0-6b-v3-int8", "parakeet-tdt-0-6b-v2-int8"):
        cfg["stt"]["model_id"] = _DEFAULT_CONFIG["stt"]["model_id"]
    from .asr.languages import WHISPER_LANGUAGES
    from .models.manifest import load_manifest

    cfg["stt"]["pinned_languages"] = list(dict.fromkeys(
        value.strip().lower() for value in cfg["stt"]["pinned_languages"]
        if isinstance(value, str) and value.strip().lower() in WHISPER_LANGUAGES))[:3]
    cfg["stt"]["fallback_budget_ms"] = max(100, min(5000, cfg["stt"]["fallback_budget_ms"]))
    models = {model["id"] for model in load_manifest()["models"] if model.get("role", "asr") == "asr"}
    cfg["stt"]["app_model_overrides"] = [
        {"app_group": item["app_group"], "model_id": item["model_id"]}
        for item in cfg["stt"]["app_model_overrides"] if isinstance(item, dict)
        and isinstance(item.get("app_group"), str) and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", item["app_group"])
        and isinstance(item.get("model_id"), str) and item["model_id"] in models]
    if not cfg["labs"]["live_preview"]:
        cfg["labs"]["use_streaming_result"] = False
    llm = cfg["llm"]
    if llm["backend"] not in ("cpu", "vulkan"):
        llm["backend"] = "cpu"
    llm["n_ctx"] = max(256, min(65536, llm["n_ctx"]))
    llm["max_tokens"] = max(1, min(4096, llm["max_tokens"]))
    llm["timeout_ms"] = max(50, min(5000, llm["timeout_ms"]))
    llm["idle_seconds"] = max(30, min(86400, llm["idle_seconds"]))
    if llm["threads"] is not None:
        llm["threads"] = max(1, min(64, llm["threads"]))
    return cfg


def migrate_settings_txt(
    settings_path: str | os.PathLike[str],
    base_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return config values migrated from legacy ``settings.txt``.

    The legacy file is read only and never modified.
    """

    if base_config is None:
        base_config = default_config()
        base_config["hotkeys"].update(speech="f9", speech_alternative="ctrl+win", speech_mouse="")
    cfg = sanitize_config(base_config)
    cfg["stt"]["engine"] = "whisper"
    cfg["stt"]["routing_enabled"] = False
    values = _read_legacy_settings(Path(settings_path))

    for legacy_key, path in _LEGACY_KEY_MAP.items():
        if legacy_key not in values:
            continue
        section_name, field_name = path
        section = cfg[section_name]
        default_value = _DEFAULT_CONFIG[section_name][field_name]
        section[field_name] = _coerce_legacy_value(values[legacy_key], default_value)

    return sanitize_config(cfg)


def _default_local_appdata() -> Path:
    configured = os.environ.get("LOCALAPPDATA")
    if configured:
        return Path(configured)
    return Path.home() / "AppData" / "Local"


def _read_json_config(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_config()
    return raw if isinstance(raw, dict) else default_config()


def _read_legacy_settings(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _sanitize_mapping(
    source: dict[str, Any],
    schema: dict[str, Any],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, rule in schema.items():
        default_value = defaults[key]
        candidate = source.get(key, default_value)
        if isinstance(rule, dict):
            nested_source = candidate if isinstance(candidate, dict) else {}
            sanitized[key] = _sanitize_mapping(nested_source, rule, default_value)
        else:
            sanitized[key] = _sanitize_scalar(candidate, default_value, rule)
    return sanitized


def _sanitize_scalar(value: Any, default_value: Any, rule: Any) -> Any:
    if _matches_schema(value, rule):
        if rule is float and isinstance(value, int):
            return float(value)
        return copy.deepcopy(value)
    return copy.deepcopy(default_value)


def _matches_schema(value: Any, rule: Any) -> bool:
    rules = rule if isinstance(rule, tuple) else (rule,)
    for item in rules:
        if item is type(None) and value is None:
            return True
        if item is bool and type(value) is bool:
            return True
        if item is int and type(value) is int:
            return True
        if item is float and type(value) in (int, float) and type(value) is not bool:
            return True
        if item is str and type(value) is str:
            return True
        if item is list and type(value) is list:
            return True
        if item is dict and type(value) is dict:
            return True
    return False


def _coerce_legacy_value(value: str, default_value: Any) -> Any:
    if isinstance(default_value, bool):
        return str(value).strip().lower() == "true"
    if isinstance(default_value, int) and not isinstance(default_value, bool):
        try:
            return int(value)
        except ValueError:
            return default_value
    if isinstance(default_value, float):
        try:
            return float(value)
        except ValueError:
            return default_value
    if default_value is None:
        try:
            return int(value)
        except ValueError:
            return None
    return str(value)
