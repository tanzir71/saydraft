from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
import copy
import json
import os
import threading

import numpy as np
import pytest

from saydraft.config import default_config,sanitize_config
from saydraft.data.audio import AudioStore
from saydraft.data.retention import AudioRetentionPolicy,expire_recordings
from saydraft.history import DictationHistoryStore,HistoryEntry

NOW=datetime(2026,11,13,12,tzinfo=timezone.utc)


def recording(tmp_path, *, days=60, name=None, path=None):
    store=DictationHistoryStore(tmp_path/"history.db")
    audio=AudioStore(tmp_path/"audio")
    path=path or audio.save(np.ones(16000,dtype=np.float32),16000)
    if name:
        renamed=path.with_name(name)
        path.rename(renamed)
        path=renamed
    old=(NOW-timedelta(days=days)).timestamp()
    os.utime(path,(old,old))
    row_id=store.append(HistoryEntry("Public editor","Original raw বাংলা العربية","Original clean.",
        "balanced","notes",1,"fixture",audio_path=str(path)))
    with store._connect() as connection:
        connection.execute("UPDATE dictations SET created_at=? WHERE id=?",((NOW-timedelta(days=days)).isoformat(),row_id))
    return store,audio,Path(path)


@pytest.mark.parametrize("enabled,days",[(False,0),(False,30),(True,0)])
def test_disabled_and_forever_policies_do_no_io(enabled,days):
    class Forbidden:
        def __getattr__(self,name):
            raise AssertionError("Inactive retention accessed saved data")
    result=expire_recordings(Forbidden(),Forbidden(),AudioRetentionPolicy(enabled,days))
    assert result.removed==result.failed==0


def test_expiry_removes_only_owned_old_audio_and_preserves_every_text_field_and_statistic(tmp_path):
    store,audio,path=recording(tmp_path)
    source=store.get_row(1)
    retry=store.append(HistoryEntry("Public editor","New retry raw","New retry clean.","balanced","notes",1,
        "fixture",audio_path=str(path),edits_json=json.dumps([{"type":"asr_retry","source_history_id":source.id}])))
    before=store.list_recent()
    with store._connect() as connection:
        stats=connection.execute("SELECT * FROM stats_daily ORDER BY day").fetchall()
    result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW)
    assert result.removed==1 and result.unavailable==result.failed==0 and not path.exists()
    assert store.list_recent()==[replace(row,audio_path=None) for row in before]
    assert store.get_row(retry).raw_text=="New retry raw"
    with store._connect() as connection:
        assert connection.execute("SELECT * FROM stats_daily ORDER BY day").fetchall()==stats


@pytest.mark.parametrize("case",["young-row","young-file","invalid-time","boundary","future"])
def test_uncertain_or_recent_audio_is_preserved(tmp_path,case):
    store,audio,path=recording(tmp_path)
    if case=="young-row":
        value=NOW.isoformat()
    elif case=="invalid-time":
        value="invalid timestamp"
    elif case=="boundary":
        value=(NOW-timedelta(days=30)).isoformat()
    elif case=="future":
        value=(NOW+timedelta(days=1)).isoformat()
    else:
        value=(NOW-timedelta(days=60)).isoformat()
        os.utime(path,(NOW.timestamp(),NOW.timestamp()))
    with store._connect() as connection:
        connection.execute("UPDATE dictations SET created_at=?",(value,))
    before=store.list_recent()
    result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW)
    assert result.removed==0 and path.is_file() and store.list_recent()==before


def test_unindexed_unmanaged_partial_and_outside_recordings_are_never_deleted(tmp_path):
    store,audio,path=recording(tmp_path,name="owner-recording.wav")
    unindexed=audio.save(np.ones(16000,dtype=np.float32))
    partial=audio.root/"public.wav.part"
    partial.write_bytes(b"public partial")
    outside=tmp_path/"0123456789abcdef0123456789abcdef.wav"
    outside.write_bytes(b"owner outside data")
    with store._connect() as connection:
        connection.execute("INSERT INTO dictations(created_at,raw_text,cleaned_text,mode,profile,model,audio_path) "
            "VALUES ('2020-01-01','public','Public','raw','notes','fixture',?)",(str(outside),))
    before=store.list_recent()
    result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW)
    assert result.removed==0 and result.skipped==2
    assert all(p.is_file() for p in (path,unindexed,partial,outside)) and store.list_recent()==before


def test_hardlinked_recording_is_preserved_without_touching_its_external_name(tmp_path):
    store,audio,path=recording(tmp_path)
    outside=tmp_path/"public-hardlink.wav"
    os.link(path,outside)
    result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW)
    assert result.skipped==1 and path.is_file() and outside.is_file()


def test_missing_expired_recording_clears_only_its_stale_audio_reference(tmp_path):
    store,audio,path=recording(tmp_path)
    original=store.get_row(1)
    path.unlink()
    result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW)
    assert result.unavailable==1 and store.get_row(1)==replace(original,audio_path=None)


def test_live_retry_lease_defers_expiry_and_is_shared_between_audio_store_instances(tmp_path):
    store,audio,path=recording(tmp_path)
    other=AudioStore(audio.root)
    entered,release=threading.Event(),threading.Event()
    def reader():
        with other.lease(path):
            entered.set()
            assert release.wait(3)
    thread=threading.Thread(target=reader)
    thread.start()
    try:
        assert entered.wait(1)
        result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW)
        assert result.skipped==1 and path.is_file() and store.get_row(1).audio_path==str(path)
    finally:
        release.set()
        thread.join(timeout=2)
    assert expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW).removed==1


def test_cancellation_and_failed_unlink_preserve_the_recording_and_metadata(tmp_path,monkeypatch):
    store,audio,path=recording(tmp_path)
    before=store.list_recent()
    result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW,cancelled=lambda:True)
    assert result.cancelled and path.is_file() and store.list_recent()==before
    def fail_unlink(self,*args,**kwargs):
        raise PermissionError("private local path")
    monkeypatch.setattr(Path,"unlink",fail_unlink)
    result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW)
    assert result.failed==1 and path.is_file() and store.list_recent()==before


def test_failed_metadata_update_after_expiry_is_repaired_by_the_next_sweep(tmp_path,monkeypatch):
    store,audio,path=recording(tmp_path)
    original=store.get_row(1)
    clear=store.clear_audio_reference
    monkeypatch.setattr(store,"clear_audio_reference",lambda path:(_ for _ in ()).throw(OSError("fixture DB busy")))
    result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW)
    assert result.removed==result.failed==1 and not path.exists() and store.get_row(1)==original
    monkeypatch.setattr(store,"clear_audio_reference",clear)
    result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW)
    assert result.unavailable==1 and store.get_row(1)==replace(original,audio_path=None)


def test_large_metadata_scan_is_paged_and_does_not_read_transcripts(tmp_path,monkeypatch):
    store,audio,path=recording(tmp_path)
    with store._connect() as connection:
        connection.executemany("INSERT INTO dictations(raw_text,cleaned_text,mode,profile,model) VALUES ('public','Public','raw','notes','fixture')",
            [()]*450)
    page=store.audio_retention_page
    sizes=[]
    def read(**kwargs):
        rows=page(**kwargs)
        sizes.append(len(rows))
        assert all(len(row)==3 for row in rows)
        return rows
    monkeypatch.setattr(store,"audio_retention_page",read)
    monkeypatch.setattr(store,"list_recent",lambda **kwargs:pytest.fail("Retention loaded transcripts"))
    result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW)
    assert result.removed==1 and sizes==[200,200,51,0]


@pytest.mark.parametrize("days",[0,1,30,3650])
def test_retention_policy_round_trips_and_legacy_enablement_stays_forever(days):
    config=default_config()
    config["recording"].update(retain_audio=True,audio_retention_days=days)
    assert AudioRetentionPolicy.from_config(sanitize_config(config))==AudioRetentionPolicy(True,days)
    legacy=copy.deepcopy(config)
    del legacy["recording"]["audio_retention_days"]
    assert AudioRetentionPolicy.from_config(sanitize_config(legacy))==AudioRetentionPolicy(True,0)


@pytest.mark.parametrize("days",[-1,3651,True])
def test_invalid_retention_bounds_preserve_forever_instead_of_enabling_expiry(days):
    config=default_config()
    config["recording"].update(retain_audio=True,audio_retention_days=days)
    assert AudioRetentionPolicy.from_config(sanitize_config(config)).days==0


@pytest.mark.parametrize("kind",["symlink-root","junction-root","reparse-file"])
def test_linked_storage_and_reparse_entries_are_preserved(tmp_path,monkeypatch,kind):
    import stat
    from types import SimpleNamespace
    store,audio,path=recording(tmp_path)
    before=store.list_recent()
    if kind=="reparse-file":
        lstat=Path.lstat
        def linked(self,*args,**kwargs):
            info=lstat(self,*args,**kwargs)
            if self==path:
                return SimpleNamespace(st_mode=info.st_mode,st_nlink=info.st_nlink,st_mtime=info.st_mtime,
                    st_file_attributes=getattr(stat,"FILE_ATTRIBUTE_REPARSE_POINT",1024))
            return info
        monkeypatch.setattr(Path,"lstat",linked)
    else:
        name="is_symlink" if kind=="symlink-root" else "is_junction"
        original=getattr(Path,name)
        monkeypatch.setattr(Path,name,lambda self:True if self==audio.root else original(self))
    result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW)
    assert result.skipped==1 and path.exists() and store.list_recent()==before


def test_external_unc_entry_is_rejected_before_any_filesystem_probe(tmp_path,monkeypatch):
    audio=AudioStore(tmp_path/"audio")
    monkeypatch.setattr(Path,"resolve",lambda *args,**kwargs:pytest.fail("UNC recording was probed"))
    assert audio.expire(r"\\public-server\share\0123456789abcdef0123456789abcdef.wav",NOW.timestamp(),
        clear_reference=lambda:pytest.fail("External metadata was cleared"))=="skipped"


def test_changed_file_identity_is_preserved_before_unlink(tmp_path,monkeypatch):
    store,audio,path=recording(tmp_path)
    lstat=Path.lstat
    calls=[]
    def changed(self,*args,**kwargs):
        if self==path:
            calls.append(True)
            if len(calls)==2:
                path.write_bytes(b"new owner replacement")
        return lstat(self,*args,**kwargs)
    monkeypatch.setattr(Path,"lstat",changed)
    result=expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW)
    assert result.skipped==1 and path.read_bytes()==b"new owner replacement"
    assert store.get_row(1).audio_path==str(path)
