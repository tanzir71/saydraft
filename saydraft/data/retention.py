"""Opt-in expiry of indexed app recordings; transcripts and statistics stay intact."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class AudioRetentionPolicy:
    enabled: bool = False
    days: int = 0  # Zero means keep forever, including legacy opt-in profiles.

    def __post_init__(self):
        if type(self.enabled) is not bool or type(self.days) is not int or not 0<=self.days<=3650:
            raise ValueError("Choose forever or 1–3650 retention days")

    @classmethod
    def from_config(cls, config):
        recording = config.get("recording", {})
        return cls(recording.get("retain_audio",False),recording.get("audio_retention_days",0))

    @property
    def expires(self):
        return self.enabled and self.days>0


@dataclass(frozen=True)
class AudioRetentionResult:
    removed: int = 0
    unavailable: int = 0
    skipped: int = 0
    failed: int = 0
    cancelled: bool = False


def _older(value, cutoff):
    try:
        created = datetime.fromisoformat(value)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return created<cutoff
    except (TypeError,ValueError,OverflowError):
        return False


def expire_recordings(history, audio, policy, *, now=None, cancelled=lambda:False):
    if not policy.expires:
        return AudioRetentionResult()
    cutoff = (now or datetime.now(timezone.utc))-timedelta(days=policy.days)
    if cutoff.tzinfo is None:
        raise ValueError("Retention time needs a timezone")
    counts = dict(removed=0,unavailable=0,skipped=0,failed=0)
    ceiling = history.audio_retention_ceiling()
    cursor = 0
    while not cancelled():
        rows = history.audio_retention_page(after_id=cursor,ceiling_id=ceiling)
        if not rows:
            break
        seen = set()
        for row_id, path, created in rows:
            cursor = row_id
            if cancelled():
                break
            if not path or not _older(created,cutoff):
                continue
            if path in seen:
                continue
            seen.add(path)
            try:
                outcome = audio.expire(path,cutoff.timestamp(),
                    clear_reference=lambda:history.clear_audio_reference(path),cancelled=cancelled)
                if outcome=="removed_unindexed":
                    counts["removed"]+=1
                    counts["failed"]+=1
                else:
                    counts[outcome]+=1
            except Exception:
                counts["failed"]+=1
    return AudioRetentionResult(**counts,cancelled=cancelled())
