import json


def test_saved_custom_recording_limits_survive_the_twenty_minute_default(tmp_path):
    from saydraft.config import load_config

    for maximum, warning in ((600, 540), (90, 0), (1800, 1740)):
        path = tmp_path / f"cap-{maximum}.json"
        expected = {"max_seconds": maximum, "warning_seconds": warning, "retain_audio": False}
        path.write_text(json.dumps({"recording": expected}), encoding="utf-8")
        config = load_config(config_path=path, settings_path=tmp_path / "absent-settings.txt")
        assert config["recording"] == expected
        assert load_config(config_path=path)["recording"] == expected


def test_shortcut_upgrade_preserves_old_bindings_and_does_not_intercept_mouse(tmp_path):
    from saydraft.config import load_config, save_config

    path = tmp_path / "config.json"
    old = {"hotkeys": {"speech": "ctrl+alt+r", "speech_alternative": "", "save": "f8", "cancel": "f12"}}
    path.write_text(json.dumps(old), encoding="utf-8")
    cfg = load_config(config_path=path, settings_path=tmp_path / "absent.txt")
    assert cfg["hotkeys"] == {**old["hotkeys"], "speech_mouse": "", "tap_lock_ms": 300}
    assert save_config(cfg, path) == cfg
    assert load_config(config_path=path, settings_path=tmp_path / "absent.txt") == cfg


def test_legacy_defaults_do_not_acquire_new_mouse_or_duplicate_f9(tmp_path):
    from saydraft.config import load_config
    from saydraft.ui.settings_window import find_hotkey_conflicts

    settings = tmp_path / "settings.txt"
    settings.write_text("speech_hotkey=f9\n", encoding="utf-8")
    cfg = load_config(config_path=tmp_path / "config.json", settings_path=settings)
    assert cfg["hotkeys"]["speech"] == "f9"
    assert cfg["hotkeys"]["speech_alternative"] == "ctrl+win"
    assert cfg["hotkeys"]["speech_mouse"] == ""
    assert not find_hotkey_conflicts(cfg["hotkeys"])


def test_fresh_profile_defaults_to_parakeet_while_existing_whisper_choice_survives(tmp_path):
    from saydraft.config import load_config

    target = tmp_path / "config.json"
    cfg = load_config(config_path=target, settings_path=tmp_path / "absent.txt")
    assert cfg["stt"]["engine"] == "parakeet"
    assert cfg["stt"]["routing_enabled"] is True
    assert cfg["stt"]["model_id"] == "parakeet-tdt-0-6b-v3-int8"
    target.write_text(json.dumps({"stt": {"model_size": "small", "language": "bn"}}), encoding="utf-8")
    cfg = load_config(config_path=target, settings_path=tmp_path / "absent.txt")
    assert cfg["stt"]["engine"] == "whisper"
    assert cfg["stt"]["model_size"] == "small"
    assert cfg["stt"]["language"] == "bn"
    assert cfg["stt"]["routing_enabled"] is False


def test_language_pins_and_overrides_sanitize_without_enabling_routing_for_old_profiles():
    from saydraft.config import sanitize_config

    cfg = sanitize_config({"stt": {"engine": "whisper", "model_size": "small",
        "pinned_languages": ["EN", None, "ar", "xx", "bn", "fr"],
        "fallback_budget_ms": 99999,
        "app_model_overrides": [None, {"app_group": "chat", "model_id": "whisper-base"},
                                {"app_group": "bad group", "model_id": "whisper-base"},
                                {"app_group": "terminal", "model_id": "unlisted"}]}})
    assert cfg["stt"]["pinned_languages"] == ["en", "ar", "bn"]
    assert cfg["stt"]["app_model_overrides"] == [{"app_group": "chat", "model_id": "whisper-base"}]
    assert cfg["stt"]["fallback_budget_ms"] == 5000
    assert cfg["stt"]["routing_enabled"] is False


def test_default_config_contains_schema_and_expected_defaults(tmp_path):
    from saydraft.config import CONFIG_SCHEMA, default_config, default_config_path

    cfg = default_config()

    assert cfg["schema_version"] == 1
    assert cfg["hotkeys"]["speech"] == "ctrl+win"
    assert cfg["hotkeys"]["speech_alternative"] == "f9"
    assert cfg["hotkeys"]["speech_mouse"] == "xbutton1"
    assert cfg["hotkeys"]["save"] == "f10"
    assert cfg["hotkeys"]["cancel"] == "esc"
    assert cfg["hotkeys"]["tap_lock_ms"] == 300
    assert cfg["app"]["auto_start_listening"] is True
    assert cfg["app"]["start_with_windows"] is False
    assert cfg["app"]["onboarded"] is False
    assert cfg["recording"]["max_seconds"] == 1200
    assert cfg["recording"]["warning_seconds"] == 1140
    assert cfg["dictation"]["mode"] == "balanced"
    assert cfg["dictation"]["profile"] == "general"
    assert cfg["dictation"]["drop_message_period"] is True
    assert cfg["dictation"]["voice_enter_enabled"] is False
    assert cfg["stt"]["model_size"] == "base"
    assert cfg["stt"]["compute_type"] == "int8"
    assert cfg["stt"]["local_files_only"] is True
    assert cfg["stt"]["silence_trim"] is True
    assert cfg["stt"]["silence_padding_ms"] == 120
    assert cfg["stt"]["vad_aggressiveness"] == 2
    assert cfg["stt"]["vad_energy_threshold"] == 0.003
    assert cfg["llm"]["enabled"] is False
    assert cfg["llm"]["model_path"] == "models/llm/model.gguf"
    assert set(CONFIG_SCHEMA) == set(cfg)
    assert default_config_path(tmp_path) == tmp_path / "Saydraft" / "config.json"


def test_load_config_writes_defaults_when_no_files_exist(tmp_path):
    from saydraft.config import load_config

    config_path = tmp_path / "config.json"

    cfg = load_config(config_path=config_path, settings_path=tmp_path / "missing-settings.txt")

    assert cfg["hotkeys"]["speech"] == "ctrl+win"
    assert config_path.exists()
    assert json.loads(config_path.read_text(encoding="utf-8")) == cfg


def test_load_config_migrates_settings_txt_once_and_keeps_old_file_untouched(tmp_path):
    from saydraft.config import load_config

    config_path = tmp_path / "config.json"
    settings_path = tmp_path / "settings.txt"
    settings_text = "\n".join(
        [
            "# keep me",
            "speech_hotkey=ctrl+shift+r",
            "save_hotkey=f8",
            "start_with_windows=true",
            "auto_start_listening=false",
            "notification_duration=7",
            "dictation_mode=aggressive",
            "format_profile=email",
            "glossary_path=custom_glossary.json",
            "app_profiles_path=custom_profiles.json",
            "llm_enabled=true",
            "llm_model_path=models/custom.gguf",
            "llm_n_ctx=4096",
            "llm_max_tokens=512",
            "llm_temperature=0.1",
            "llm_top_p=0.8",
            "llm_threads=4",
            "llm_gpu_layers=1",
        ]
    )
    settings_path.write_text(settings_text, encoding="utf-8")

    cfg = load_config(config_path=config_path, settings_path=settings_path)

    assert cfg["hotkeys"] == {
        "speech": "ctrl+shift+r",
        "speech_alternative": "ctrl+win",
        "speech_mouse": "",
        "save": "f8",
        "cancel": "esc",
        "tap_lock_ms": 300,
    }
    assert cfg["app"]["start_with_windows"] is True
    assert cfg["app"]["auto_start_listening"] is False
    assert cfg["app"]["notification_duration"] == 7
    assert cfg["recording"]["max_seconds"] == 1200
    assert cfg["recording"]["warning_seconds"] == 1140
    assert cfg["dictation"]["mode"] == "aggressive"
    assert cfg["dictation"]["profile"] == "email"
    assert cfg["dictation"]["glossary_path"] == "custom_glossary.json"
    assert cfg["dictation"]["app_profiles_path"] == "custom_profiles.json"
    assert cfg["llm"]["enabled"] is True
    assert cfg["llm"]["model_path"] == "models/custom.gguf"
    assert cfg["llm"]["n_ctx"] == 4096
    assert cfg["llm"]["max_tokens"] == 512
    assert cfg["llm"]["temperature"] == 0.1
    assert cfg["llm"]["top_p"] == 0.8
    assert cfg["llm"]["threads"] == 4
    assert cfg["llm"]["gpu_layers"] == 1
    assert settings_path.read_text(encoding="utf-8") == settings_text
    assert json.loads(config_path.read_text(encoding="utf-8")) == cfg

    settings_path.write_text("speech_hotkey=changed-after-migration", encoding="utf-8")
    assert load_config(config_path=config_path, settings_path=settings_path) == cfg


def test_existing_config_ignores_unknown_keys_and_fills_missing_defaults(tmp_path):
    from saydraft.config import load_config

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "hotkeys": {"speech": "f7", "unused": "drop-me"},
                "dictation": {"profile": "notes"},
                "unknown_top_level": True,
                "llm": {"enabled": "not-a-bool", "threads": None},
            }
        ),
        encoding="utf-8",
    )

    cfg = load_config(config_path=config_path, settings_path=tmp_path / "settings.txt")

    assert cfg["hotkeys"] == {
        "speech": "f7",
        "speech_alternative": "ctrl+win",
        "speech_mouse": "",
        "save": "f10",
        "cancel": "esc",
        "tap_lock_ms": 300,
    }
    assert cfg["dictation"]["mode"] == "balanced"
    assert cfg["dictation"]["profile"] == "notes"
    assert cfg["llm"]["enabled"] is False
    assert cfg["llm"]["threads"] is None
    assert "unknown_top_level" not in cfg
    assert "unused" not in cfg["hotkeys"]
    assert json.loads(config_path.read_text(encoding="utf-8")) == cfg


def test_main_initializes_logging_and_config_before_qt_shell(monkeypatch, tmp_path):
    import sys
    import types

    import saydraft.config as config
    import saydraft.logging_config as logging_config
    import saydraft.main as main

    calls = []
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr("saydraft.compat.migrate.migrate_autostart", lambda manager: False)
    monkeypatch.setattr(logging_config, "configure_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(config, "load_config", lambda: calls.append("config"))
    class FakeQtApp:
        def run(self):
            calls.append("qt")
            return 0

    monkeypatch.setitem(
        sys.modules,
        "saydraft.app",
        types.SimpleNamespace(SaydraftApp=lambda: FakeQtApp()),
    )

    assert main.main() == 0

    assert calls == ["logging", "config", "qt"]


def test_cleanup_sidecar_settings_are_bounded_without_reinterpreting_legacy_gpu_layers():
    from saydraft.config import default_config, sanitize_config

    cfg = default_config()
    cfg["llm"].update(backend="remote", n_ctx=-1, max_tokens=0, timeout_ms=-20,
                      idle_seconds=0, threads=999, gpu_layers=17)
    clean = sanitize_config(cfg)["llm"]
    assert clean["backend"] == "cpu" and clean["n_ctx"] == 256 and clean["max_tokens"] == 1
    assert clean["timeout_ms"] == 50 and clean["idle_seconds"] == 30 and clean["threads"] == 64
    assert clean["gpu_layers"] == 17
