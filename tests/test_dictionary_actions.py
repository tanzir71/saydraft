from types import SimpleNamespace as NS

import pytest

from saydraft.dictation.glossary import load_glossary
from tests.test_correction_session import rig, record, suggestions


def ready(tmp_path):
    r = rig(tmp_path)
    path = tmp_path / "glossary.json"
    cleaner = r.worker.services.cleaner
    cleaner.cfg = NS(glossary_path=str(path))
    cleaner.glossary = load_glossary(path)
    cleaner.reload_glossary = lambda: setattr(cleaner, "glossary", load_glossary(path))
    record(r)
    r.observation.ticket.done.set()
    r.worker.poll_corrections()
    r.executor.drain()
    return r, suggestions(r)[0], path


def changes(r):
    return [args[0] for name, args in r.signals if name == "dictionary_changed"]


def test_explicit_add_runs_serially_once_and_reloads_cleaner_then_undoes(tmp_path, caplog):
    r, suggestion, path = ready(tmp_path)
    assert r.worker.add_correction(suggestion)
    assert not path.exists() and r.worker.busy
    assert not r.worker.add_correction(suggestion)
    r.executor.drain()
    change, = changes(r)
    assert change.status == "added" and change.receipt.term == "Kubernetes"
    assert r.worker.services.cleaner.glossary.user_terms == ("Kubernetes",)
    assert not r.worker.is_current_correction(suggestion)
    assert len(r.store.list_recent()) == 1 and "Kubernet" not in caplog.text
    assert r.worker.undo_correction(change.receipt)
    r.executor.drain()
    assert changes(r)[-1].status == "undone"
    assert r.worker.services.cleaner.glossary.user_terms == ()
    r.worker.shutdown()


@pytest.mark.parametrize("reason", ["automatic_off", "learning_off", "busy", "cancelled", "shutdown"])
def test_disallowed_add_never_mutates_dictionary(tmp_path, reason):
    r, suggestion, path = ready(tmp_path)
    if reason == "learning_off":
        r.worker.services.config["dictation"]["learn_corrections"] = False
    elif reason == "busy":
        r.worker._inflight = 1
    elif reason == "cancelled":
        r.worker.cancel()
    elif reason == "shutdown":
        r.worker.shutdown()
    assert not r.worker.add_correction(suggestion, automatic=reason == "automatic_off")
    assert not path.exists()
    r.worker._inflight = 0
    r.worker.shutdown()


def test_auto_add_can_be_cancelled_before_queued_write(tmp_path):
    r, suggestion, path = ready(tmp_path)
    r.worker.services.config["dictation"]["auto_add_dictionary"] = True
    assert r.worker.add_correction(suggestion, automatic=True)
    r.worker.cancel()
    r.executor.drain()
    assert not path.exists() and changes(r)[-1].status == "obsolete"
    r.worker.shutdown()


def test_auto_add_and_later_manual_claim_prevent_undo(tmp_path):
    from saydraft.dictation.glossary import learn_word
    r, suggestion, path = ready(tmp_path)
    r.worker.services.config["dictation"]["auto_add_dictionary"] = True
    assert r.worker.add_correction(suggestion, automatic=True)
    r.executor.drain()
    receipt = changes(r)[-1].receipt
    learn_word(path, "Kubernetes")
    assert r.worker.undo_correction(receipt)
    r.executor.drain()
    assert changes(r)[-1].status == "stale"
    assert load_glossary(path).user_terms == ("Kubernetes",)
    r.worker.shutdown()


def test_failed_write_emits_private_object_without_word_logging(tmp_path, caplog):
    r, suggestion, path = ready(tmp_path)
    path.write_bytes(b"{broken")
    assert r.worker.add_correction(suggestion)
    r.executor.drain()
    assert changes(r)[-1].status == "error" and path.read_bytes() == b"{broken"
    assert "Kubernet" not in caplog.text
    r.worker.shutdown()


def test_refresh_failure_keeps_successful_add_receipt_for_undo(tmp_path):
    r, suggestion, path = ready(tmp_path)
    def fail():
        raise ValueError("authored refresh failure")
    r.worker.services.cleaner.reload_glossary = fail
    assert r.worker.add_correction(suggestion)
    r.executor.drain()
    change = changes(r)[-1]
    assert change.status == "added" and change.receipt
    assert load_glossary(path).user_terms == ("Kubernetes",)
    r.worker.shutdown()


def test_queue_failure_is_reported_without_mutation_or_stuck_busy(tmp_path):
    r, suggestion, path = ready(tmp_path)
    def fail(*args):
        raise RuntimeError("authored executor failure")
    r.executor.submit = fail
    assert not r.worker.add_correction(suggestion)
    assert changes(r)[-1].status == "error" and not path.exists() and not r.worker.busy
    r.worker.shutdown()
