import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from saydraft.dictionary import store
from saydraft.dictation.glossary import learn_word, load_glossary


def test_learning_receipt_survives_restart_and_undo_preserves_unrelated_data(tmp_path):
    path = tmp_path / "glossary.json"
    original = {"protected_terms": ["ACME"], "replacements": {"sea sharp": "C#"}, "custom": [1, "বাংলা"]}
    path.write_text(json.dumps(original), encoding="utf-8")
    receipt = store.add_term(path, "Kubernetes", learned=True)
    learn_word(path, "Saydraft")
    assert store.read_dictionary(path).data["_saydraft_learning"][receipt.key]["term"] == "Kubernetes"
    assert load_glossary(path).user_terms == ("Kubernetes", "Saydraft")
    assert store.undo_learning(path, receipt)
    assert not store.undo_learning(path, receipt)
    saved = store.read_dictionary(path).data
    assert saved == {**original, "user_terms": ["Saydraft"]}


def test_manual_claim_revokes_learning_undo(tmp_path):
    path = tmp_path / "glossary.json"
    receipt = store.add_term(path, "Kubernetes", learned=True)
    learn_word(path, "kubernetes")
    assert not store.undo_learning(path, receipt)
    assert load_glossary(path).user_terms == ("Kubernetes",)
    assert "_saydraft_learning" not in store.read_dictionary(path).data


def test_case_change_undo_restores_manual_spelling(tmp_path):
    path = tmp_path / "glossary.json"
    learn_word(path, "github")
    receipt = store.add_term(path, "GitHub", learned=True)
    assert load_glossary(path).user_terms == ("GitHub",)
    assert store.undo_learning(path, receipt)
    assert load_glossary(path).user_terms == ("github",)
    assert "_saydraft_learning" not in store.read_dictionary(path).data


def test_newer_learning_and_restored_value_revoke_older_undo(tmp_path):
    path = tmp_path / "glossary.json"
    first = store.add_term(path, "github", learned=True)
    second = store.add_term(path, "GitHub", learned=True)
    assert not store.undo_learning(path, first)
    assert store.undo_learning(path, second)
    assert not store.undo_learning(path, first)
    assert load_glossary(path).user_terms == ("github",)


@pytest.mark.parametrize("terms,protected", [(["GitHub"], []), (["github", "GitHub"], []), ([], ["github"])])
def test_learning_noop_for_same_spelling_ambiguous_duplicates_or_protected(tmp_path, terms, protected):
    path = tmp_path / "glossary.json"
    raw = json.dumps({"user_terms": terms, "protected_terms": protected}).encode()
    path.write_bytes(raw)
    assert store.add_term(path, "GitHub", learned=True) is None
    assert path.read_bytes() == raw


def test_nfc_equivalent_casefolded_manual_terms_deduplicate(tmp_path):
    path = tmp_path / "glossary.json"
    learn_word(path, "Café")
    learn_word(path, "CAFE\u0301")
    assert load_glossary(path).user_terms == ("Café",)


def test_parallel_app_writers_keep_every_term(tmp_path):
    path = tmp_path / "glossary.json"
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: learn_word(path, f"Term{i}"), range(32)))
    assert set(load_glossary(path).user_terms) == {f"Term{i}" for i in range(32)}
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("raw", [b"", b"{broken", b"[]", b'\xff', b'{"user_terms": [1]}',
    b'{"replacements": []}', b'{"_saydraft_learning": []}', b" " * (4 * 1024 * 1024 + 1)],
    ids=["empty", "broken", "array", "encoding", "terms", "pairs", "metadata", "oversized"])
def test_invalid_dictionary_is_never_overwritten(tmp_path, raw):
    path = tmp_path / "glossary.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        learn_word(path, "Kubernetes")
    assert path.read_bytes() == raw
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_replace_failure_keeps_original_and_removes_temporary(tmp_path, monkeypatch):
    path = tmp_path / "glossary.json"
    learn_word(path, "Original")
    raw = path.read_bytes()
    def fail(*args):
        raise OSError("authored replacement failure")
    monkeypatch.setattr(store.os, "replace", fail)
    with pytest.raises(OSError):
        store.add_term(path, "Kubernetes", learned=True)
    assert path.read_bytes() == raw
    assert not list(tmp_path.glob("*.tmp"))


def test_external_edit_during_staging_wins(tmp_path, monkeypatch):
    path = tmp_path / "glossary.json"
    learn_word(path, "Original")
    raw = b'{"user_terms": ["External"]}'
    fsync = store.os.fsync
    def concurrent_write(fd):
        fsync(fd)
        path.write_bytes(raw)
    monkeypatch.setattr(store.os, "fsync", concurrent_write)
    with pytest.raises(store.DictionaryConflict):
        store.add_term(path, "Kubernetes", learned=True)
    assert path.read_bytes() == raw
    assert not list(tmp_path.glob("*.tmp"))


def test_stale_settings_snapshot_cannot_overwrite_new_learning(tmp_path):
    path = tmp_path / "glossary.json"
    snapshot = store.read_dictionary(path)
    store.add_term(path, "Kubernetes", learned=True)
    with pytest.raises(store.DictionaryConflict):
        store.save_dictionary(path, {"user_terms": ["Old editor"]}, expected_revision=snapshot.revision)
    assert load_glossary(path).user_terms == ("Kubernetes",)


def test_editor_keeps_unmodified_provenance_but_revokes_changed_term(tmp_path):
    path = tmp_path / "glossary.json"
    first = store.add_term(path, "Kubernetes", learned=True)
    other = store.add_term(path, "GitHub", learned=True)
    snapshot = store.read_dictionary(path)
    edited = {**snapshot.data, "user_terms": ["Kubernetes", "GITHUB", "Manual"]}
    store.save_dictionary(path, edited, expected_revision=snapshot.revision)
    assert not store.undo_learning(path, other)
    assert store.undo_learning(path, first)
    assert load_glossary(path).user_terms == ("GITHUB", "Manual")


def test_raw_editor_cannot_resurrect_an_old_receipt(tmp_path):
    path = tmp_path / "glossary.json"
    receipt = store.add_term(path, "Kubernetes", learned=True)
    old = store.read_dictionary(path)
    learn_word(path, "Kubernetes")
    current = store.read_dictionary(path)
    store.save_dictionary(path, old.data, expected_revision=current.revision)
    assert not store.undo_learning(path, receipt)
    assert load_glossary(path).user_terms == ("Kubernetes",)


def test_undo_is_bound_to_original_dictionary_not_a_copied_file(tmp_path):
    path = tmp_path / "glossary.json"
    receipt = store.add_term(path, "Kubernetes", learned=True)
    other = tmp_path / "copy.json"
    other.write_bytes(path.read_bytes())
    assert not store.undo_learning(other, receipt)
    assert load_glossary(other).user_terms == ("Kubernetes",)
    assert store.undo_learning(path, receipt)
