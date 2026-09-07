"""Tests for the daily reset: at midnight, and at startup after a missed one."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events, async_fire_time_changed

from custom_components.star_jar.const import EVENT_UPDATED
from homeassistant.core import HomeAssistant

# The integration follows Home Assistant's configured time zone. The test harness
# defaults to US/Pacific, so pin the household's zone explicitly: midnight has to
# be local midnight, not UTC and not whatever the harness picked.
LOCAL_TZ = "America/New_York"
EVENING = "2026-09-07 20:00:00-04:00"
JUST_PAST_MIDNIGHT = "2026-09-08 00:00:05-04:00"
TWO_DAYS_LATER = "2026-09-09 12:00:00-04:00"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config.async_set_time_zone(LOCAL_TZ)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_stars_today_resets_at_local_midnight_and_nothing_else_moves(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_config_entry: MockConfigEntry
):
    freezer.move_to(EVENING)
    await _setup(hass, mock_config_entry)
    events = async_capture_events(hass, EVENT_UPDATED)
    await mock_config_entry.runtime_data.async_award(1, "x", "chore")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.robin_stars_today").state == "1"

    freezer.move_to(JUST_PAST_MIDNIGHT)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.robin_stars_today").state == "0"
    assert hass.states.get("sensor.robin_star_jar").state == "1"
    assert len(mock_config_entry.runtime_data.data.ledger) == 1
    assert len(events) == 1


async def test_startup_after_a_missed_midnight_resets_today(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_config_entry: MockConfigEntry
):
    freezer.move_to(EVENING)
    await _setup(hass, mock_config_entry)
    await mock_config_entry.runtime_data.async_award(1, "x", "chore")
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    freezer.move_to(TWO_DAYS_LATER)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.robin_stars_today").state == "0"
    assert hass.states.get("sensor.robin_star_jar").state == "1"


async def test_an_award_after_a_missed_midnight_rolls_the_day_first(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_config_entry: MockConfigEntry
):
    freezer.move_to(EVENING)
    await _setup(hass, mock_config_entry)
    await mock_config_entry.runtime_data.async_award(1, "x", "chore")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.robin_stars_today").state == "1"

    freezer.move_to(TWO_DAYS_LATER)
    await mock_config_entry.runtime_data.async_award(1, "y", "chore")
    await hass.async_block_till_done()

    assert hass.states.get("sensor.robin_stars_today").state == "1"
    assert hass.states.get("sensor.robin_star_jar").state == "2"


async def test_restart_on_the_same_day_keeps_today(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_config_entry: MockConfigEntry
):
    freezer.move_to(EVENING)
    await _setup(hass, mock_config_entry)
    await mock_config_entry.runtime_data.async_award(2, "x", "chore")
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.robin_stars_today").state == "2"
