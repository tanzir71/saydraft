"""Shared style selection and deterministic cleanup levels for live/preview paths."""

from dataclasses import dataclass
from .language import english_rules_allowed

TONES = frozenset({"formal", "casual", "very_casual"})
GROUP_DEFAULTS = {"messages": "casual", "work_chat": "casual", "email": "formal",
    "docs": "formal", "code": "casual", "ai_chat": "casual", "general": "casual"}
_PROFILE_TONES = {"email": "formal", "chat": "casual"}


@dataclass(frozen=True)
class Style:
    tone: str
    intensity: int


def style_for(context):
    tone = getattr(context, "tone", None)
    if tone not in TONES:
        tone = _PROFILE_TONES.get(context.profile, "neutral")
    intensity = context.intensity
    if type(intensity) is not int or not 1 <= intensity <= 4:
        intensity = 4 if context.mode == "aggressive" else 3
    return Style(tone, 0 if context.mode == "raw" else intensity)


def style_fields(value):
    if not isinstance(value, dict):
        return {}
    fields = {}
    if isinstance(value.get("tone"), str) and value["tone"] in TONES:
        fields["tone"] = value["tone"]
    if type(value.get("intensity")) is int and 1 <= value["intensity"] <= 4:
        fields["intensity"] = value["intensity"]
    return fields


def sanitize_styles(value):
    if not isinstance(value, dict):
        return {}
    return {group: fields for group in GROUP_DEFAULTS
        if (fields := style_fields(value.get(group)))}


def select_style(options, group, override=()):
    group = group if group in GROUP_DEFAULTS else "general"
    profile = options.get("profile", "general")
    mode = options.get("mode", "balanced")
    fields = {"tone": _PROFILE_TONES.get(profile, GROUP_DEFAULTS[group]),
        "intensity": 4 if mode == "aggressive" else 3}
    fields.update(sanitize_styles(options.get("styles", {})).get(group, {}))
    fields.update(style_fields(override))
    return Style(**fields)


def rule_options(context):
    # Local import avoids the dictation package's compatibility re-export cycle.
    from saydraft.dictation.rules import RuleOptions
    style = style_for(context)
    level = style.intensity
    english = english_rules_allowed(context.language)
    structured = context.profile in ("notes", "email") or (
        context.tone is not None and context.app_group in ("docs", "email"))
    return RuleOptions(
        remove_fillers=english and level >= 2, aggressive_fillers=english and level == 4,
        remove_repetitions=english and level >= 3, handle_self_corrections=english and level == 4,
        normalize_punctuation=english and level >= 1,
        normalize_capitalization=english and level >= 2 and style.tone != "very_casual",
        normalize_whitespace=True, enable_list_formatting=english and level >= 2 and structured,
        convert_spoken_punctuation=english and level == 4,
        convert_spoken_newlines=english and level >= 2 and structured,
        final_period=False, normalize_itn=english and level >= 2, intensity=level,
        number_style="compact" if context.profile == "notes" else "prose")
