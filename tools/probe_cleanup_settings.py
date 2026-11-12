"""Replay licensed cleanup setup and Apply in an isolated offscreen Settings profile."""

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from saydraft.config import default_config, load_config, save_config
from saydraft.models.cleanup import download_cleanup_model
from saydraft.models.downloader import installation_ready
from saydraft.models.hardware import save_report
from saydraft.models.manifest import get_model
from saydraft.privacy.netguard import NetworkGuard


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("models-dir", "hardware-report", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--model", default="qwen35-2b-q4-k-m")
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="vulkan")
    args = parser.parse_args(argv)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6 import QtGui, QtWidgets
    from saydraft.ui.settings_page import SettingsPage

    args.output.mkdir(parents=True, exist_ok=False)
    config_path = args.output / "config.json"
    cfg = default_config()
    cfg["dictation"]["glossary_path"] = str((args.output / "glossary.json").resolve())
    cfg["dictation"]["app_profiles_path"] = str((args.output / "app_profiles.json").resolve())
    save_config(cfg, config_path)
    before = hashlib.sha256(config_path.read_bytes()).hexdigest()
    hardware = json.loads(args.hardware_report.read_text(encoding="utf-8"))
    save_report(hardware.get("hardware", hardware), args.output / "hardware-benchmarks")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    if os.name == "nt":
        QtGui.QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts/segoeui.ttf"))
        app.setFont(QtGui.QFont("Segoe UI", 10))
    applied, window = [], None
    report = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "delivery": "isolated QA profile; no microphone, hooks, history or insertion",
        "model": args.model, "backend": args.backend}
    NetworkGuard.install()
    try:
        def download(model, backend, progress, *, pause_event):
            return download_cleanup_model(model, backend, progress, models_dir=args.models_dir, pause_event=pause_event)
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("Unexpected HTTP request")) as network:
            window = SettingsPage(config_path=config_path, snippets_path=args.output / "snippets.txt",
                autostart_manager=SimpleNamespace(is_enabled=lambda: False, set_enabled=lambda _value: None),
                cleanup_download_callback=download, on_config_applied=applied.append)
            window.show_tab("models")
            window.resize(760, 560)
            window.show()
            picker = window.cleanup_picker
            picker.combo.setCurrentIndex(picker.combo.findData(args.model))
            picker.backend.setCurrentIndex(picker.backend.findData(args.backend))
            app.processEvents()
            window.grab().save(str(args.output / "models-top.png"))
            picker.download_button.click()
            deadline = time.monotonic() + 180
            while picker.task is not None and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.005)
            if picker.task is not None:
                raise TimeoutError("Settings setup did not finish")
            path = Path(window.llm_path_edit.text())
            report["network_requests"] = network.call_count
            report["verified_model"] = installation_ready(get_model(args.model), path.parent, check_hashes=True)
            report["config_unchanged_before_apply"] = hashlib.sha256(config_path.read_bytes()).hexdigest() == before
            report["cleanup_still_disabled"] = not window.llm_enabled_checkbox.isChecked()
            window.llm_enabled_checkbox.setChecked(True)
            report["applied"] = window.apply_changes()
            saved = load_config(config_path=config_path)
            report["applied_path_backend"] = (saved["llm"]["model_path"] == str(path)
                and saved["llm"]["backend"] == args.backend and saved["llm"]["enabled"])
            report["speech_unchanged"] = saved["stt"] == cfg["stt"]
            page = window.tabs.currentWidget()
            page.ensureWidgetVisible(window.llm_path_edit)
            app.processEvents()
            window.grab().save(str(args.output / "models-bottom.png"))
    except BaseException as error:
        report["error_type"] = type(error).__name__
    finally:
        if window is not None:
            window.close()
        NetworkGuard.uninstall()
        report["probe_complete"] = (report.get("network_requests") == 0 and len(applied) == 1 and all(report.get(key)
            for key in ("verified_model", "config_unchanged_before_apply", "cleanup_still_disabled", "applied",
                        "applied_path_backend", "speech_unchanged")) and not report.get("error_type"))
        with (args.output / "report.json").open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
        print(json.dumps(report), flush=True)
    return 0 if report["probe_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
