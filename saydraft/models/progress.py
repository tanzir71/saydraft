"""Immutable, public artifact metadata for explicit download progress."""

from dataclasses import dataclass

from .manifest import safe_filename


@dataclass(frozen=True)
class FileProgress:
    model_id: str
    filename: str
    completed_bytes: int
    total_bytes: int
    phase: str

    def __post_init__(self):
        if (not safe_filename(self.model_id) or not safe_filename(self.filename)
                or type(self.completed_bytes) is not int or type(self.total_bytes) is not int
                or not 0 <= self.completed_bytes <= self.total_bytes or self.total_bytes <= 0
                or self.phase not in ("checking", "downloading", "verifying", "verified")):
            raise ValueError("Invalid model file progress")
