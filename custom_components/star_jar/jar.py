"""The star jar state machine, as pure functions over plain data.

Nothing here touches Home Assistant. Every rule in the design spec's
constraint 4 lives in this file, so the tests for it need no fixtures:

* the active jar only ever accumulates toward ``jar_size``; each time it fills
  it empties into one reward in ``rewards_available``, carrying overflow;
* ``redeem`` spends one reward and refuses at zero;
* a negative ``adjust`` floors at zero and never touches rewards.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .const import LEDGER_LIMIT, JarAction


class JarEmptyError(Exception):
    """Raised when redeeming with no reward available."""


@dataclass(frozen=True)
class LedgerEntry:
    """One award, adjust, or redeem, exactly as it happened."""

    at: datetime
    action: JarAction
    stars: int
    reason: str
    source: str
    jar_before: int
    jar_after: int
    jar_filled: bool
    reward: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage and for sensor attributes."""
        return {
            "at": self.at.isoformat(),
            "action": str(self.action),
            "stars": self.stars,
            "reason": self.reason,
            "source": self.source,
            "jar_before": self.jar_before,
            "jar_after": self.jar_after,
            "jar_filled": self.jar_filled,
            "reward": self.reward,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LedgerEntry:
        """Deserialize from storage."""
        at = dt_util.parse_datetime(data["at"])
        if at is None:
            msg = f"Unreadable ledger timestamp: {data['at']!r}"
            raise ValueError(msg)
        return cls(
            at=at,
            action=JarAction(data["action"]),
            stars=int(data["stars"]),
            reason=str(data["reason"]),
            source=str(data["source"]),
            jar_before=int(data["jar_before"]),
            jar_after=int(data["jar_after"]),
            jar_filled=bool(data["jar_filled"]),
            reward=data.get("reward"),
        )


@dataclass(frozen=True)
class JarState:
    """Everything the integration persists for one child."""

    jar: int = 0
    stars_today: int = 0
    today: date | None = None
    rewards_available: int = 0
    rewards_redeemed: int = 0
    ledger: tuple[LedgerEntry, ...] = ()
    narration: str | None = None

    @property
    def last_entry(self) -> LedgerEntry | None:
        """The newest ledger entry, or None before the first star."""
        return self.ledger[-1] if self.ledger else None

    @property
    def last_message_entry(self) -> LedgerEntry | None:
        """The newest award or redeem. Adjustments are bookkeeping and never carry a message."""
        for entry in reversed(self.ledger):
            if entry.action is not JarAction.ADJUST:
                return entry
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "jar": self.jar,
            "stars_today": self.stars_today,
            "today": self.today.isoformat() if self.today else None,
            "rewards_available": self.rewards_available,
            "rewards_redeemed": self.rewards_redeemed,
            "ledger": [entry.to_dict() for entry in self.ledger],
            "narration": self.narration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JarState:
        """Deserialize from storage. Missing keys take their defaults."""
        today_raw = data.get("today")
        return cls(
            jar=int(data.get("jar", 0)),
            stars_today=int(data.get("stars_today", 0)),
            today=date.fromisoformat(today_raw) if today_raw else None,
            rewards_available=int(data.get("rewards_available", 0)),
            rewards_redeemed=int(data.get("rewards_redeemed", 0)),
            ledger=tuple(LedgerEntry.from_dict(item) for item in data.get("ledger", [])),
            narration=data.get("narration"),
        )


@dataclass(frozen=True)
class Transition:
    """A state change and the ledger entry that describes it."""

    state: JarState
    entry: LedgerEntry


def roll_day(state: JarState, today: date) -> JarState:
    """Reset the daily count when the date has moved on. Returns the same object when it has not."""
    if state.today == today:
        return state
    return replace(state, stars_today=0, today=today)


def _record(state: JarState, entry: LedgerEntry, **changes: Any) -> Transition:
    """Apply field changes, append the entry, drop narration that no longer describes the state."""
    ledger = (*state.ledger, entry)[-LEDGER_LIMIT:]
    return Transition(state=replace(state, ledger=ledger, narration=None, **changes), entry=entry)


def _add(  # noqa: PLR0917 - the positional signature is the module's fixed interface
    state: JarState, stars: int, reason: str, source: str, now: datetime, jar_size: int, action: JarAction
) -> Transition:
    """Add stars to the active jar. Every full jar becomes one reward, carrying overflow."""
    total = state.jar + stars
    filled = total // jar_size
    jar_after = total % jar_size
    entry = LedgerEntry(
        at=now,
        action=action,
        stars=stars,
        reason=reason,
        source=source,
        jar_before=state.jar,
        jar_after=jar_after,
        jar_filled=filled > 0,
    )
    return _record(
        state,
        entry,
        jar=jar_after,
        stars_today=state.stars_today + stars,
        rewards_available=state.rewards_available + filled,
    )


def award(  # noqa: PLR0917 - the positional signature is the module's fixed interface
    state: JarState, stars: int, reason: str, source: str, now: datetime, jar_size: int
) -> Transition:
    """Grant one or more stars."""
    if stars < 1:
        msg = "An award needs at least one star"
        raise ValueError(msg)
    return _add(state, stars, reason, source, now, jar_size, JarAction.AWARD)


def adjust(  # noqa: PLR0917 - the positional signature is the module's fixed interface
    state: JarState, stars: int, reason: str, source: str, now: datetime, jar_size: int
) -> Transition:
    """Reconcile by a signed delta.

    A positive delta is an award in all but name. A negative delta floors
    the active jar and today's count at zero and never touches rewards.
    """
    if stars == 0:
        msg = "An adjustment needs a non-zero delta"
        raise ValueError(msg)
    if stars > 0:
        return _add(state, stars, reason, source, now, jar_size, JarAction.ADJUST)
    jar_after = max(0, state.jar + stars)
    entry = LedgerEntry(
        at=now,
        action=JarAction.ADJUST,
        stars=stars,
        reason=reason,
        source=source,
        jar_before=state.jar,
        jar_after=jar_after,
        jar_filled=False,
    )
    return _record(state, entry, jar=jar_after, stars_today=max(0, state.stars_today + stars))


def redeem(state: JarState, reward: str, now: datetime) -> Transition:
    """Spend one available reward. The active jar is untouched."""
    if state.rewards_available < 1:
        raise JarEmptyError
    entry = LedgerEntry(
        at=now,
        action=JarAction.REDEEM,
        stars=0,
        reason=reward,
        source="redeem",
        jar_before=state.jar,
        jar_after=state.jar,
        jar_filled=False,
        reward=reward,
    )
    return _record(
        state,
        entry,
        rewards_available=state.rewards_available - 1,
        rewards_redeemed=state.rewards_redeemed + 1,
    )
