# Person 1 owns this file: Decision yes or no with a reason.
from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str | None = None

    @classmethod
    def yes(cls) -> "Decision":
        return cls(allowed=True)

    @classmethod
    def no(cls, reason: str) -> "Decision":
        return cls(allowed=False, reason=reason)
