import json

import pytest

from saydraft.dictionary.portable import export_dictionary, prepare_import
from saydraft.dictionary.store import (DictionaryConflict, add_term, entry_source, read_dictionary,
    save_dictionary, term_key, undo_learning, validate_dictionary_edit)
from saydraft.dictation.glossary import Glossary, apply_replacements


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_import_is_a_staged_merge_with_existing_case_pairs_and_owner_data_retained(tmp_path):
    path = write(tmp_path / "incoming.json", {"user_terms": ["SAYDRAFT", "বাংলা"], "protected_terms": ["C#"],
        "replacements": {"sea sharp": "Wrong", "my folder": r"C:\new\bin"}, "owner": "incoming", "new_extension": {"value": 3}})
    original = {"user_terms": ["Saydraft"], "replacements": {"sea sharp": "C#"}, "owner": "keep"}
    result = prepare_import(original, path)
    assert original == {"user_terms": ["Saydraft"], "replacements": {"sea sharp": "C#"}, "owner": "keep"}
    assert (result.added, result.skipped, result.conflicts) == (3, 1, 1)
    assert result.data["user_terms"] == ["Saydraft", "বাংলা"]
    assert result.data["replacements"] == {"sea sharp": "C#", "my folder": r"C:\new\bin"}
    assert result.data["owner"] == "keep" and result.data["new_extension"] == {"value": 3}


def test_imported_sources_survive_save_and_are_not_in_portable_data_or_receipts(tmp_path):
    source = write(tmp_path / "source.json", {"user_terms": ["Kubernetes"], "protected_terms": ["C#"],
        "replacements": {"sea sharp": "C#"}, "_saydraft_learning": {"fake": {"revision": "forged"}}})
    target = tmp_path / "glossary.json"
    before = read_dictionary(target)
    imported = prepare_import(before.editable, source)
    saved = save_dictionary(target, imported.data, expected_revision=before.revision, imports=imported.imports)
    assert entry_source(saved, "user_terms", "Kubernetes") == "Imported"
    assert entry_source(saved, "protected_terms", "C#") == "Imported"
    assert entry_source(saved, "replacements", "sea sharp", "C#") == "Imported"
    assert "_saydraft_learning" not in saved.data and "_saydraft_imports" not in saved.editable
    exported = tmp_path / "export.json"
    export_dictionary(exported, saved.data)
    assert json.loads(exported.read_text("utf-8")) == saved.editable
    unchanged = save_dictionary(target, saved.editable, expected_revision=saved.revision)
    assert entry_source(unchanged, "user_terms", "Kubernetes") == "Imported"


def test_learned_case_change_can_undo_back_to_imported_origin_after_an_unrelated_save(tmp_path):
    path = tmp_path / "glossary.json"
    incoming = write(tmp_path / "import.json", {"user_terms": ["kubernetes"]})
    snapshot = read_dictionary(path)
    imported = prepare_import(snapshot.editable, incoming)
    save_dictionary(path, imported.data, expected_revision=snapshot.revision, imports=imported.imports)
    receipt = add_term(path, "Kubernetes", learned=True)
    learned = read_dictionary(path)
    assert entry_source(learned, "user_terms", "Kubernetes") == "Learned"
    edited = {**learned.editable, "protected_terms": ["Owner term"]}
    save_dictionary(path, edited, expected_revision=learned.revision)
    assert undo_learning(path, receipt)
    restored = read_dictionary(path)
    assert entry_source(restored, "user_terms", "kubernetes") == "Imported"


def test_manual_claim_of_unchanged_learned_or_imported_terms_revokes_the_previous_origin(tmp_path):
    path = tmp_path / "glossary.json"
    receipt = add_term(path, "Kubernetes", learned=True)
    snapshot = read_dictionary(path)
    saved = save_dictionary(path, snapshot.editable, expected_revision=snapshot.revision,
        manual_claims=[("user_terms", "Kubernetes")])
    assert entry_source(saved, "user_terms", "Kubernetes") == "Manual" and not undo_learning(path, receipt)
    imported = prepare_import(saved.editable, write(tmp_path / "import.json", {"user_terms": ["Django"]}))
    saved = save_dictionary(path, imported.data, expected_revision=saved.revision, imports=imported.imports)
    add_term(path, "Django")
    assert entry_source(read_dictionary(path), "user_terms", "Django") == "Manual"


def test_changed_imported_pairs_become_manual_and_forged_raw_metadata_is_ignored(tmp_path):
    path = tmp_path / "glossary.json"
    original = read_dictionary(path)
    imported = prepare_import(original.editable, write(tmp_path / "import.json", {"replacements": {"sea sharp": "C#"}}))
    saved = save_dictionary(path, imported.data, expected_revision=original.revision, imports=imported.imports)
    changed = {**saved.editable, "replacements": {"sea sharp": "CSharp"}, "user_terms": ["Forged"],
        "_saydraft_imports": {"user_terms": {"forged": {"term": "Forged"}}}}
    saved = save_dictionary(path, changed, expected_revision=saved.revision)
    assert entry_source(saved, "replacements", "sea sharp", "CSharp") == "Manual"
    assert entry_source(saved, "user_terms", "Forged") == "Manual"


def test_staged_import_cannot_overwrite_learning_since_the_editor_snapshot(tmp_path):
    path = tmp_path / "glossary.json"
    snapshot = read_dictionary(path)
    imported = prepare_import(snapshot.editable, write(tmp_path / "import.json", {"user_terms": ["Django"]}))
    receipt = add_term(path, "Kubernetes", learned=True)
    with pytest.raises(DictionaryConflict):
        save_dictionary(path, imported.data, expected_revision=snapshot.revision, imports=imported.imports)
    assert read_dictionary(path).data["user_terms"] == ["Kubernetes"]
    assert undo_learning(path, receipt)


def test_import_accepts_utf8_bom_and_preserves_literal_unicode_and_backslashes(tmp_path):
    path = tmp_path / "import.json"
    data = {"user_terms": ["বাংলা", "العربية"], "replacements": {"folder": r"C:\new\bin\1"}}
    path.write_text(json.dumps(data, ensure_ascii=False), "utf-8-sig")
    imported = prepare_import({}, path)
    assert imported.data == {**data, "protected_terms": []}
    assert apply_replacements("folder", Glossary(replacements=tuple(data["replacements"].items()))) == r"C:\new\bin\1"


def test_invalid_or_oversized_imports_do_not_change_existing_data(tmp_path):
    current = {"user_terms": ["Keep"]}
    for raw in (b'{broken', b'{"protected_terms":[1]}', b'x' * (4 * 1024 * 1024 + 1)):
        path = tmp_path / "import.json"
        path.write_bytes(raw)
        with pytest.raises(ValueError):
            prepare_import(current, path)
        assert current == {"user_terms": ["Keep"]}


def test_complete_staged_payload_budget_includes_private_source_metadata(tmp_path):
    snapshot = read_dictionary(tmp_path / "unused.json")
    term = "x" * (2 * 1024 * 1024)
    with pytest.raises(ValueError, match="4 MB"):
        validate_dictionary_edit(snapshot, {"user_terms": [term]},
            imports={"user_terms": {term_key(term): {"term": term}}})


def test_atomic_export_failure_preserves_destination_bytes(tmp_path, monkeypatch):
    destination = tmp_path / "export.json"
    destination.write_bytes(b'previous owner file')
    def fail(*args):
        raise OSError("fixture replacement failure")
    monkeypatch.setattr("saydraft.dictionary.store.os.replace", fail)
    with pytest.raises(OSError):
        export_dictionary(destination, {"user_terms": ["Kubernetes"]})
    assert destination.read_bytes() == b'previous owner file'
    assert not list(tmp_path.glob("*.tmp"))
