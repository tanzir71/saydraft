import threading
import time
from types import SimpleNamespace

from saydraft.core.audio_retention import AudioRetention,AudioRetentionUpdate
from saydraft.data.retention import AudioRetentionPolicy,AudioRetentionResult,expire_recordings
from tests.test_session_worker import Timer,make_worker
from tests.test_audio_retention import recording,NOW


def settle(owner):
    deadline=time.monotonic()+3
    while owner._running and time.monotonic()<deadline:
        time.sleep(.003)
    assert not owner._running


def test_inactive_owner_never_starts_threads_or_touches_data():
    owner=AudioRetention(object(),object(),AudioRetentionPolicy(True,0),
        sweep=lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError("Forever swept data")))
    assert not owner.request() and owner._pool is None
    owner.close()


def test_owner_serializes_requests_and_reschedules_without_gui_wait():
    entered,release,done=threading.Event(),threading.Event(),threading.Event()
    updates,timers=[],[]
    def sweep(*args,cancelled):
        entered.set()
        assert release.wait(3)
        return AudioRetentionResult()
    def changed(update):
        updates.append(update)
        if update.state=="ready":
            done.set()
    def timer(seconds,callback):
        timers.append(Timer(seconds,callback))
        return timers[-1]
    owner=AudioRetention(None,None,AudioRetentionPolicy(True,30),sweep=sweep,changed=changed,timer_factory=timer)
    try:
        assert owner.request() and entered.wait(1) and not owner.request()
        release.set()
        assert done.wait(2)
        settle(owner)
        deadline=time.monotonic()+2
        while (not timers or not timers[0].started) and time.monotonic()<deadline:
            time.sleep(.003)
        assert timers[0].seconds==900 and timers[0].started
        assert [u.state for u in updates]==["working","ready"]
    finally:
        release.set()
        owner.close()
    assert timers[0].cancelled


def test_closing_owner_cancels_blocked_work_and_suppresses_stale_feedback():
    entered,release=threading.Event(),threading.Event()
    updates=[]
    def sweep(*args,cancelled):
        entered.set()
        assert release.wait(3)
        assert cancelled()
        return AudioRetentionResult(cancelled=True)
    owner=AudioRetention(None,None,AudioRetentionPolicy(True,30),sweep=sweep,changed=updates.append)
    try:
        assert owner.request() and entered.wait(1)
        owner.close()
        release.set()
        settle(owner)
        assert [u.state for u in updates]==["working"] and not owner.request()
    finally:
        release.set()
        owner.close()


def test_current_worker_rejects_old_owner_status_but_refreshes_committed_metadata_changes():
    worker,_,_,_,events,_=make_worker()
    worker._retention_generation=9
    policy=AudioRetentionPolicy(True,30)
    worker._audio_retention_changed(8,AudioRetentionUpdate(policy,"ready",AudioRetentionResult(removed=1)))
    assert events==[("history_updated",0)]
    worker._audio_retention_changed(9,AudioRetentionUpdate(policy,"working"))
    assert events[-1][0]=="audio_retention_updated"
    worker.shutdown()


def test_retired_owner_still_reports_already_committed_metadata_changes():
    entered,release,done=threading.Event(),threading.Event(),threading.Event()
    updates=[]
    def sweep(*args,cancelled):
        entered.set()
        assert release.wait(3)
        return AudioRetentionResult(removed=1,cancelled=cancelled())
    def changed(update):
        updates.append(update)
        if update.state=="retired":
            done.set()
    owner=AudioRetention(None,None,AudioRetentionPolicy(True,30),sweep=sweep,changed=changed)
    try:
        assert owner.request() and entered.wait(1)
        owner.close()
        release.set()
        assert done.wait(2) and updates[-1].result.removed==1
        assert owner._timer is None
    finally:
        release.set()
        owner.close()


def test_worker_retry_lease_preserves_audio_until_the_complete_review_is_persisted(tmp_path):
    store,audio,path=recording(tmp_path)
    worker,_,executor,_,signals,_=make_worker(queued=True)
    worker.services.audio_store,worker.services.history=audio,store
    worker.services.processor.history=store
    entered,release=threading.Event(),threading.Event()
    def transcribe(samples):
        entered.set()
        assert release.wait(3)
        return "Public retry words"
    worker.services.retry_asr=SimpleNamespace(transcribe=transcribe,model_id="fixture",last_language="en",last_timings={})
    source=store.get_row(1)
    assert worker.retry_history(source)
    thread=threading.Thread(target=executor.drain)
    thread.start()
    try:
        assert entered.wait(1)
        assert expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW).skipped==1
        assert path.exists()
    finally:
        release.set()
        thread.join(timeout=3)
    assert not thread.is_alive() and len(store.list_recent())==2
    assert expire_recordings(store,audio,AudioRetentionPolicy(True,30),now=NOW).removed==1
    assert all(row.audio_path is None for row in store.list_recent())
    assert store.get_row(source.id)==type(source)(**{**vars(source),"audio_path":None})
    assert any(event[0]=="history_retry_finished" for event in signals)
    worker.shutdown()
