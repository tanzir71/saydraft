"""Persisted engine selection, including compatibility with old Whisper configs."""

from .sherpa_parakeet import DEFAULT_MODEL


def configured_model_id(config):
    stt = config.get("stt", {})
    if stt.get("engine", "whisper") == "parakeet":
        return stt.get("model_id", DEFAULT_MODEL)
    return "whisper-" + stt.get("model_size", "base")


def select_model(config, model_id):
    stt = config["stt"]
    if model_id.startswith("whisper-"):
        stt["engine"] = "whisper"
        stt["model_size"] = model_id.removeprefix("whisper-")
    else:
        stt["engine"] = "parakeet"
        stt["model_id"] = model_id


def create_asr(config):
    if config["stt"].get("engine", "whisper") == "parakeet":
        from .sherpa_parakeet import ParakeetConfig, ParakeetEngine

        return ParakeetEngine(ParakeetConfig.from_app_config(config))
    from saydraft.stt.whisper_engine import WhisperEngine, WhisperEngineConfig

    return WhisperEngine(WhisperEngineConfig.from_app_config(config))
