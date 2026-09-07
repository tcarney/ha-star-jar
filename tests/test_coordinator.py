"""Tests for StarJarCoordinator: atomic mutations, persistence, and the event."""

from __future__ import annotations

import asyncio

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from custom_components.star_jar.const import EVENT_UPDATED
from custom_components.star_jar.jar import JarEmptyError
from custom_components.star_jar.store import StarJarStore
from homeassistant.core import HomeAssistant


async def test_award_updates_data_and_persists(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    coordinator = loaded_entry.runtime_data

    entry = await coordinator.async_award(2, "made bed", "chore")

    assert entry.stars == 2
    assert coordinator.data.jar == 2
    assert coordinator.data.stars_today == 2
    assert (await StarJarStore(hass, loaded_entry.entry_id).async_load()).jar == 2


async def test_award_fires_the_event_with_the_full_payload(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    events = async_capture_events(hass, EVENT_UPDATED)
    coordinator = loaded_entry.runtime_data

    await coordinator.async_award(3, "big job", "parent")
    await hass.async_block_till_done()

    assert len(events) == 1
    payload = events[0].data
    assert payload["action"] == "award"
    assert payload["stars"] == 3
    assert payload["reason"] == "big job"
    assert payload["source"] == "parent"
    assert payload["reward"] is None
    assert payload["jar_before"] == 0
    assert payload["jar"] == 3
    assert payload["jar_filled"] is False
    assert payload["rewards_available"] == 0
    assert payload["stars_today"] == 3


async def test_rollover_is_flagged_in_the_event(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    events = async_capture_events(hass, EVENT_UPDATED)
    coordinator = loaded_entry.runtime_data

    await coordinator.async_adjust(23, "seed", "adjust")
    await coordinator.async_award(2, "over the top", "chore")
    await hass.async_block_till_done()

    assert events[-1].data["jar_filled"] is True
    assert events[-1].data["jar"] == 1
    assert events[-1].data["rewards_available"] == 1


async def test_redeem_event_carries_the_reward(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    events = async_capture_events(hass, EVENT_UPDATED)
    coordinator = loaded_entry.runtime_data
    await coordinator.async_adjust(24, "seed", "adjust")

    await coordinator.async_redeem("movie night")
    await hass.async_block_till_done()

    assert events[-1].data["action"] == "redeem"
    assert events[-1].data["reward"] == "movie night"
    assert coordinator.data.rewards_available == 0
    assert coordinator.data.rewards_redeemed == 1


async def test_redeem_at_zero_raises_and_changes_nothing(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    events = async_capture_events(hass, EVENT_UPDATED)
    coordinator = loaded_entry.runtime_data

    with pytest.raises(JarEmptyError):
        await coordinator.async_redeem("movie night")
    await hass.async_block_till_done()

    assert coordinator.data.rewards_redeemed == 0
    assert events == []


async def test_concurrent_awards_are_all_counted(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    coordinator = loaded_entry.runtime_data

    original_save = coordinator.store.async_save

    # The mocked store never yields to the event loop, so without a forced
    # suspension inside the lock this test would pass even with the lock removed.
    async def yielding_save(state):
        await asyncio.sleep(0)
        await original_save(state)

    coordinator.store.async_save = yielding_save  # type: ignore[method-assign] - force a real suspension inside the lock

    await asyncio.gather(*(coordinator.async_award(1, f"r{i}", "chore") for i in range(5)))

    assert coordinator.data.jar == 5
    assert len(coordinator.data.ledger) == 5
