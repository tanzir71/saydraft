"""Explicit performance checks use fresh owned inference, never filename guesses."""

from types import SimpleNamespace

import pytest

from saydraft.cleanup.llm.client import CleanupClient
from saydraft.cleanup.llm.sidecar import SidecarReply
from saydraft.dictation import DictationConfig, DictationPipeline
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner


def live_client(meta=None):
    calls = []
    manager = SimpleNamespace(generation=1, prepare=lambda: True)
    responses = {"data": [{"id": "private/path/not-a-size.gguf", "meta":
        meta if meta is not None else {"n_params": 2_030_000_000, "size": 1_396_198_496}}]}
    def request(path, **kwargs):
        calls.append((path, kwargs))
        return responses if path == "/v1/models" else {
            "content": "discard generated prose", "timings": {"predicted_n": 60, "predicted_per_second": 30}}
    def run(operation, *, timeout):
        return SidecarReply(operation(SimpleNamespace(request_json=request), 100), "ok")
    manager.run = run
    return CleanupClient(manager), calls


def test_client_refreshes_three_samples_uses_live_metadata_and_invalidates_prefix():
    client, calls = live_client()
    assert client.calibrate_decoder().reason == "calibrated" and len(calls) == 3
    client._prefix = (1, "stale prefix")
    rows = client.benchmark()
    assert rows == [{"parameters_b": 2.03, "tokens": 60, "seconds": 2}] * 3
    assert [path for path, _ in calls] == ["/completion"] * 3 + ["/v1/models"] + ["/completion"] * 3
    assert client._prefix is None and "discard" not in repr(rows) and "private" not in repr(rows)
    assert all(kwargs["deadline"] == 100 for _, kwargs in calls)


@pytest.mark.parametrize("meta", [{}, {"n_params": True, "size": 3}, {"n_params": 2, "size": True},
    {"n_params": 2.0, "size": 3}, {"n_params": 0, "size": 3}, {"n_params": 2, "size": -1}])
def test_invalid_metadata_never_generates_or_guesses_from_filename(meta):
    client, calls = live_client(meta)
    with pytest.raises(RuntimeError, match="metadata"):
        client.benchmark()
    assert [path for path, _ in calls] == ["/v1/models"]


def test_instance_change_between_metadata_and_generation_refuses_measurement():
    client, calls = live_client()
    original = client.manager.run
    def run(operation, **kwargs):
        result = original(operation, **kwargs)
        client.manager.generation += 1
        return result
    client.manager.run = run
    with pytest.raises(RuntimeError, match="metadata"):
        client.benchmark()
    assert len(calls) == 1 and client.decoder.current is None


def test_disabled_cleaner_never_constructs_runtime_and_pipeline_delegates_only_explicitly():
    def forbidden(*args, **kwargs):
        raise AssertionError("Must not construct a runtime")
    cleaner = LocalLLMCleaner(LocalLLMConfig(), manager_factory=forbidden)
    pipeline = DictationPipeline(DictationConfig(), llm_cleaner=cleaner)
    assert pipeline.benchmark() == []
    assert cleaner._manager is None


@pytest.mark.parametrize("failure", [False, True])
def test_cleaner_settles_background_work_invalidates_and_reprimes_even_after_failure(failure):
    client, _ = live_client()
    cleaner = LocalLLMCleaner(LocalLLMConfig(enabled=True, model_path="installed.gguf"))
    cleaner._client = client
    calls = []
    cleaner._preparation = SimpleNamespace(wait=lambda timeout: calls.append(("wait", timeout)) or True,
        invalidate=lambda: calls.append("invalidate"), request=lambda hints: calls.append(("prime", hints)))
    def measure():
        calls.append("measure")
        if failure:
            raise RuntimeError("measurement failed")
        return ["timings"]
    client.benchmark = measure
    if failure:
        with pytest.raises(RuntimeError, match="measurement failed"):
            cleaner.benchmark()
    else:
        assert cleaner.benchmark() == ["timings"]
    assert calls[:3] == [("wait", 185), "invalidate", "measure"]
    assert calls[3][0] == "prime" and calls[3][1].post_rules and not calls[3][1].before_caret


def test_unsettled_background_work_cannot_overlap_benchmark():
    cleaner = LocalLLMCleaner(LocalLLMConfig(enabled=True, model_path="installed.gguf"))
    cleaner._client = SimpleNamespace()
    cleaner._preparation = SimpleNamespace(wait=lambda timeout: False)
    with pytest.raises(RuntimeError, match="still running"):
        cleaner.benchmark()
