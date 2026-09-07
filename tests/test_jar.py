"""Tests for the pure jar state machine. No Home Assistant involved."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from custom_components.star_jar.const import LEDGER_LIMIT, JarAction
from custom_components.star_jar.jar import JarEmptyError, JarState, LedgerEntry, adjust, award, redeem, roll_day

NOW = datetime(2026, 9, 7, 18, 30, tzinfo=UTC)
SIZE = 24


def test_award_adds_to_jar_and_today():
    result = award(JarState(), 1, "made bed", "chore", NOW, SIZE)

    assert result.state.jar == 1
    assert result.state.stars_today == 1
    assert result.state.rewards_available == 0
    assert result.entry == LedgerEntry(
        at=NOW,
        action=JarAction.AWARD,
        stars=1,
        reason="made bed",
        source="chore",
        jar_before=0,
        jar_after=1,
        jar_filled=False,
    )
    assert result.state.ledger == (result.entry,)


def test_award_rolls_over_and_carries_overflow():
    result = award(JarState(jar=22), 3, "big job", "parent", NOW, SIZE)

    assert result.state.jar == 1
    assert result.state.rewards_available == 1
    assert result.entry.jar_filled is True
    assert result.entry.jar_before == 22
    assert result.entry.jar_after == 1


def test_award_exactly_full_leaves_an_empty_jar():
    result = award(JarState(jar=23), 1, "x", "chore", NOW, SIZE)

    assert result.state.jar == 0
    assert result.state.rewards_available == 1
    assert result.entry.jar_filled is True


def test_award_leaves_redeemed_count_alone():
    result = award(JarState(jar=5, rewards_available=1, rewards_redeemed=2), 2, "x", "chore", NOW, SIZE)

    assert result.state.rewards_available == 1
    assert result.state.rewards_redeemed == 2


@pytest.mark.parametrize("stars", [0, -1])
def test_award_rejects_non_positive(stars):
    with pytest.raises(ValueError):
        award(JarState(), stars, "x", "chore", NOW, SIZE)


def test_adjust_positive_behaves_like_an_award():
    result = adjust(JarState(jar=23), 2, "physical jar count", "adjust", NOW, SIZE)

    assert result.state.jar == 1
    assert result.state.rewards_available == 1
    assert result.state.stars_today == 2
    assert result.entry.action is JarAction.ADJUST
    assert result.entry.jar_filled is True


def test_adjust_negative_floors_at_zero_and_keeps_rewards():
    result = adjust(JarState(jar=2, stars_today=1, rewards_available=1), -5, "double counted", "adjust", NOW, SIZE)

    assert result.state.jar == 0
    assert result.state.stars_today == 0
    assert result.state.rewards_available == 1
    assert result.entry.stars == -5
    assert result.entry.jar_before == 2
    assert result.entry.jar_after == 0
    assert result.entry.jar_filled is False


def test_adjust_rejects_zero():
    with pytest.raises(ValueError):
        adjust(JarState(), 0, "x", "adjust", NOW, SIZE)


def test_redeem_spends_one_reward_and_leaves_the_active_jar():
    result = redeem(JarState(jar=7, rewards_available=1), "movie night", NOW)

    assert result.state.rewards_available == 0
    assert result.state.rewards_redeemed == 1
    assert result.state.jar == 7
    assert result.entry.action is JarAction.REDEEM
    assert result.entry.reward == "movie night"
    assert result.entry.stars == 0
    assert result.entry.jar_before == result.entry.jar_after == 7


def test_redeem_refuses_when_no_reward_is_available():
    with pytest.raises(JarEmptyError):
        redeem(JarState(jar=23), "anything", NOW)


def test_roll_day_resets_today_only_when_the_date_changes():
    state = JarState(jar=5, stars_today=3, today=date(2026, 9, 7))

    assert roll_day(state, date(2026, 9, 7)) is state

    rolled = roll_day(state, date(2026, 9, 8))
    assert rolled.stars_today == 0
    assert rolled.jar == 5
    assert rolled.today == date(2026, 9, 8)


def test_ledger_is_capped_oldest_first():
    state = JarState()
    for i in range(LEDGER_LIMIT + 5):
        state = award(state, 1, f"r{i}", "chore", NOW, SIZE).state

    assert len(state.ledger) == LEDGER_LIMIT
    assert state.ledger[0].reason == "r5"
    assert state.ledger[-1].reason == f"r{LEDGER_LIMIT + 4}"


def test_any_mutation_clears_stale_narration():
    state = JarState(rewards_available=1, narration="old words")

    assert award(state, 1, "x", "chore", NOW, SIZE).state.narration is None
    assert adjust(state, -1, "x", "adjust", NOW, SIZE).state.narration is None
    assert redeem(state, "r", NOW).state.narration is None


def test_last_entry_is_none_when_empty_and_newest_otherwise():
    assert JarState().last_entry is None
    state = award(JarState(), 1, "first", "chore", NOW, SIZE).state
    state = award(state, 1, "second", "chore", NOW, SIZE).state
    assert state.last_entry is not None
    assert state.last_entry.reason == "second"


def test_last_message_entry_skips_adjustments():
    assert JarState().last_message_entry is None

    only_adjusted = adjust(JarState(), 1, "seed", "adjust", NOW, SIZE).state
    only_adjusted = adjust(only_adjusted, -1, "recount", "adjust", NOW, SIZE).state
    assert only_adjusted.last_message_entry is None

    state = award(JarState(), 1, "a", "chore", NOW, SIZE).state
    state = adjust(state, -1, "x", "adjust", NOW, SIZE).state
    state = adjust(state, 2, "y", "adjust", NOW, SIZE).state
    assert state.last_message_entry is not None
    assert state.last_message_entry.reason == "a"

    state = award(JarState(rewards_available=1), 1, "a", "chore", NOW, SIZE).state
    state = redeem(state, "r", NOW).state
    state = adjust(state, 1, "z", "adjust", NOW, SIZE).state
    assert state.last_message_entry is not None
    assert state.last_message_entry.action is JarAction.REDEEM
    assert state.last_message_entry.reward == "r"


def test_state_round_trips_through_dict():
    state = JarState(today=date(2026, 9, 7), rewards_available=1, narration="hello")
    state = award(state, 2, "x", "chore", NOW, SIZE).state
    state = redeem(state, "movie night", NOW).state
    state = adjust(state, -1, "recount", "adjust", NOW, SIZE).state

    assert JarState.from_dict(state.to_dict()) == state
