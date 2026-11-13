"""Explicit disposable-runner verification; never called by desktop startup."""

import ctypes


def require_disposable_runner():
    import os
    import sys
    if sys.platform != "win32" or os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise RuntimeError("Verification is restricted to disposable GitHub-hosted Windows runners")


def download_probe(directory):
    from pathlib import Path
    from saydraft.models.downloader import download_model
    from saydraft.models.manifest import get_model
    from saydraft.models.errors import download_failure_message
    source = get_model("whisper-base")
    file = next(file for file in source["files"] if file["path"] == "config.json")
    model = {**source, "files": [file]}
    try:
        download_model(model, Path(directory))
        return {"downloaded": True}
    except Exception as error:
        message = download_failure_message(error)
        return {"downloaded": False, "error_type": type(error).__name__,
                "firewall_recovery_message": "remove Saydraft’s block rule" in message,
                "resume_message": "Download to resume" in message}


def frozen_smoke(model_directory, report_directory):
    """Public fixture through frozen ASR/rules/History, plus real network controls."""
    require_disposable_runner()
    from pathlib import Path
    import sys
    import tempfile
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Frozen application required")
    result = {"complete": False, "frozen": True, "microphone_used": False,
              "audio_devices_enumerated": False, "owner_clipboard_accessed": False,
              "input_injected": False, "scope": "packaged public-fixture ASR, rules and temporary History; separate source probe covers full worker/memory insertion"}
    from .netguard import NetworkGuard
    from .telemetry import configure_process_privacy
    NetworkGuard.install()
    configure_process_privacy()
    pipeline = None
    try:
        from saydraft.models.manifest import get_model
        from saydraft.models.downloader import installation_ready
        if not installation_ready(get_model("whisper-base"), Path(model_directory), check_hashes=True):
            raise ValueError("Pinned speech fixture is incomplete")
        result["network"] = native_http()
        with tempfile.TemporaryDirectory(prefix="firewall-runtime-", dir=report_directory) as temporary:
            result["download"] = download_probe(Path(temporary) / "model-file")
            import soundfile as sf
            from saydraft.models.benchmark import fixture_path
            from saydraft.stt.whisper_engine import WhisperEngine, WhisperEngineConfig
            from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
            from saydraft.history import DictationHistoryStore, HistoryEntry
            audio, rate = sf.read(fixture_path(), dtype="float32")
            if rate != 16000 or audio.shape != (128000,):
                raise ValueError("Invalid public fixture")
            engine = WhisperEngine(WhisperEngineConfig(model_size=str(model_directory), local_files_only=True))
            raw = engine.transcribe(audio[:48000])
            pipeline = DictationPipeline(DictationConfig())
            cleaned = pipeline.process_transcript(raw, DictationContext())
            store = DictationHistoryStore(Path(temporary) / "history.db")
            store.append(HistoryEntry("Firewall fixture", raw, cleaned, "balanced", "general", 3.0, "whisper-base"))
            rows = store.list_recent(limit=1)
            result["asr_nonempty"] = bool(raw.strip())
            result["cleaned_nonempty"] = bool(cleaned.strip())
            result["history_matches"] = bool(rows and rows[0].raw_text == raw and rows[0].cleaned_text == cleaned)
            if "sounddevice" in sys.modules:
                result["audio_devices_enumerated"] = None
                raise RuntimeError("Audio capture runtime initialized during the owned fixture check")
            result["complete"] = all(result[name] for name in ("asr_nonempty", "cleaned_nonempty", "history_matches"))
    except Exception as error:
        result["error_type"] = type(error).__name__
        trace = error.__traceback__
        while trace.tb_next is not None:
            trace = trace.tb_next
        result["error_location"] = {"file": Path(trace.tb_frame.f_code.co_filename).name, "line": trace.tb_lineno}
    finally:
        try:
            if pipeline is not None:
                pipeline.close()
        except Exception as error:
            result["complete"] = False
            result["shutdown_error_type"] = type(error).__name__
        finally:
            NetworkGuard.uninstall()
    return result


def native_http():
    """A fixed credential-free WinHTTP request, bypassing Python socket hooks."""
    from ctypes import wintypes as w
    api = ctypes.WinDLL("winhttp", use_last_error=True)
    signatures = {
        "WinHttpOpen": ([w.LPCWSTR, w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD], w.HANDLE),
        "WinHttpConnect": ([w.HANDLE, w.LPCWSTR, w.WORD, w.DWORD], w.HANDLE),
        "WinHttpOpenRequest": ([w.HANDLE, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, ctypes.c_void_p, w.DWORD], w.HANDLE),
        "WinHttpSetTimeouts": ([w.HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int], w.BOOL),
        "WinHttpSendRequest": ([w.HANDLE, w.LPCWSTR, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.c_size_t], w.BOOL),
        "WinHttpReceiveResponse": ([w.HANDLE, ctypes.c_void_p], w.BOOL),
        "WinHttpQueryHeaders": ([w.HANDLE, w.DWORD, w.LPCWSTR, ctypes.c_void_p, ctypes.POINTER(w.DWORD), ctypes.c_void_p], w.BOOL),
        "WinHttpCloseHandle": ([w.HANDLE], w.BOOL),
    }
    for name, (args, result) in signatures.items():
        method = getattr(api, name)
        method.argtypes, method.restype = args, result
    handles = []
    try:
        session = api.WinHttpOpen("Saydraft-disposable-firewall-probe", 1, None, None, 0)  # no proxy
        if not session:
            raise ctypes.WinError(ctypes.get_last_error())
        handles.append(session)
        if not api.WinHttpSetTimeouts(session, 3000, 3000, 3000, 3000):
            raise ctypes.WinError(ctypes.get_last_error())
        connection = api.WinHttpConnect(session, "api.github.com", 443, 0)
        if not connection:
            raise ctypes.WinError(ctypes.get_last_error())
        handles.append(connection)
        request = api.WinHttpOpenRequest(connection, "GET", "/repos/tanzir71/saydraft/releases/latest", None, None, None, 0x800000)
        if not request:
            raise ctypes.WinError(ctypes.get_last_error())
        handles.append(request)
        # Disable redirects: no second host is contacted by this probe.
        api.WinHttpSetOption.argtypes = [w.HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD]
        api.WinHttpSetOption.restype = w.BOOL
        policy = w.DWORD(0)  # WINHTTP_OPTION_REDIRECT_POLICY_NEVER
        if not api.WinHttpSetOption(request, 88, ctypes.byref(policy), ctypes.sizeof(policy)):
            raise ctypes.WinError(ctypes.get_last_error())
        disabled = w.DWORD(0x1 | 0x2 | 0x4)  # cookies, redirects, automatic authentication
        if not api.WinHttpSetOption(request, 63, ctypes.byref(disabled), ctypes.sizeof(disabled)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not api.WinHttpSendRequest(request, None, 0, None, 0, 0, 0) or not api.WinHttpReceiveResponse(request, None):
            raise ctypes.WinError(ctypes.get_last_error())
        code, size = w.DWORD(), w.DWORD(ctypes.sizeof(w.DWORD))
        if not api.WinHttpQueryHeaders(request, 19 | 0x20000000, None, ctypes.byref(code), ctypes.byref(size), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"reachable": True, "http_status": code.value}
    except OSError as error:
        return {"reachable": False, "winerror": error.winerror}
    finally:
        for handle in reversed(handles):
            api.WinHttpCloseHandle(handle)

