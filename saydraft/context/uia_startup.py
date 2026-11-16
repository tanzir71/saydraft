"""Package-only UIA initialization check; never obtain a field or send input."""

import threading


def _inspect(action, *, factory=None, timeout=10):
    if factory is None:
        from .uia_native import NativeUIAReader
        factory = NativeUIAReader
    done = threading.Event()
    results = []

    def run():
        reader = None
        try:
            reader = factory()
            result = action(reader)
            reader.close()
            reader = None
            results.append(result)
        except Exception:
            pass  # Provider exceptions must not expose text or environment data.
        finally:
            if reader is not None:
                try:
                    reader.close()
                except Exception:
                    pass
            done.set()

    threading.Thread(target=run, name="Saydraft-UIA-package-check", daemon=True).start()
    if not done.wait(timeout) or not results:
        raise RuntimeError("Windows field verification could not initialize")
    return results[0]


def verify_initialization(*, factory=None, timeout=10):
    return _inspect(lambda _reader: True, factory=factory, timeout=timeout)


def field_metadata(window, *, factory=None, timeout=10):
    """Explicit diagnostic: focus/password/type/identity only, never field text."""
    from .focused_edit import read_focused_edit

    def inspect(reader):
        field = read_focused_edit(reader, window, include_text=False)
        return dict(status=field.status, is_password=field.is_password,
                    control_type=field.control_type, identity_length=len(field.runtime_id))

    return _inspect(inspect, factory=factory, timeout=timeout)


def metadata_main(argv):
    import argparse
    import json
    from pathlib import Path
    from .foreground import NativeForegroundApi
    from saydraft.privacy.netguard import NetworkGuard

    parser = argparse.ArgumentParser(description="Explicit read-only field metadata diagnostic; no text or input")
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Output exists; retain it and choose a fresh file")
    NetworkGuard.install()
    api = NativeForegroundApi()
    window = api.foreground()
    report = dict(metadata_only=True, text_read=False, clipboard_accessed=False,
                  audio_opened=False, input_injected=False)
    try:
        report.update(field_metadata(int(window)))
        report['window_unchanged'] = api.foreground() == window
        report['complete'] = True
    except Exception:
        report.update(status="unavailable", complete=False)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report['complete'] else 1
