"""Tests for the sensor platform."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from custom_components.star_jar.const import DOMAIN, EVENT_UPDATED
from custom_components.star_jar.sensor import NO_STARS_YET, StarJarSensor
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

ENTITY_IDS = [
    "sensor.robin_star_jar",
    "sensor.robin_stars_today",
    "sensor.robin_rewards_available",
    "sensor.robin_rewards_redeemed",
    "sensor.robin_star_message",
]


async def test_five_sensors_on_one_device_named_for_the_child(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, loaded_entry.entry_id)})
    assert device is not None
    assert device.name == "Robin"

    registry = er.async_get(hass)
    for entity_id in ENTITY_IDS:
        assert hass.states.get(entity_id) is not None, entity_id
        registered = registry.async_get(entity_id)
        assert registered is not None
        assert registered.device_id == device.id


async def test_initial_states(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    for entity_id in ENTITY_IDS[:4]:
        assert hass.states.get(entity_id).state == "0", entity_id

    jar = hass.states.get("sensor.robin_star_jar")
    assert jar.attributes["jar_size"] == 24
    assert jar.attributes["stars_to_fill"] == 24
    assert jar.attributes["last_event"] is None
    assert jar.attributes["recent"] == []

    message = hass.states.get("sensor.robin_star_message")
    assert message.state == NO_STARS_YET
    assert message.attributes["message"] == NO_STARS_YET


async def test_states_follow_an_award(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    await loaded_entry.runtime_data.async_award(2, "making the bed", "chore")
    await hass.async_block_till_done()

    assert hass.states.get("sensor.robin_star_jar").state == "2"
    assert hass.states.get("sensor.robin_stars_today").state == "2"
    jar_attrs = hass.states.get("sensor.robin_star_jar").attributes
    assert jar_attrs["stars_to_fill"] == 22
    assert jar_attrs["last_event"]["reason"] == "making the bed"
    assert len(jar_attrs["recent"]) == 1

    message = hass.states.get("sensor.robin_star_message")
    assert message.state == "+2 stars for making the bed. 2 of 24."
    assert message.attributes["message"] == message.state
    assert message.attributes["action"] == "award"
    assert message.attributes["stars"] == 2
    assert message.attributes["reason"] == "making the bed"
    assert message.attributes["source"] == "chore"
    assert message.attributes["reward"] is None
    assert message.attributes["at"].startswith("20")


async def test_rollover_and_redeem_read_through(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    coordinator = loaded_entry.runtime_data
    await coordinator.async_adjust(23, "seed", "adjust")
    await coordinator.async_award(2, "the last one", "chore")
    await hass.async_block_till_done()

    assert hass.states.get("sensor.robin_star_jar").state == "1"
    assert hass.states.get("sensor.robin_rewards_available").state == "1"
    assert hass.states.get("sensor.robin_star_message").state == "+2 stars for the last one. Jar full! 1 reward ready."

    await coordinator.async_redeem("movie night")
    await hass.async_block_till_done()

    assert hass.states.get("sensor.robin_rewards_available").state == "0"
    assert hass.states.get("sensor.robin_rewards_redeemed").state == "1"
    assert hass.states.get("sensor.robin_star_jar").state == "1"
    assert hass.states.get("sensor.robin_star_message").state == "Redeemed: movie night. 0 rewards left."


async def test_single_star_wording_survives_an_adjustment(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    coordinator = loaded_entry.runtime_data
    await coordinator.async_award(1, "feeding the cat", "chore")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.robin_star_message").state == "+1 star for feeding the cat. 1 of 24."

    await coordinator.async_adjust(-1, "counted twice", "adjust")
    await hass.async_block_till_done()
    # The adjustment reconciles the count but never speaks for itself: the award's line stands, refreshed.
    assert hass.states.get("sensor.robin_star_message").state == "+1 star for feeding the cat. 0 of 24."


async def test_an_adjustment_regenerates_the_message_with_current_counts(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
):
    coordinator = loaded_entry.runtime_data
    await coordinator.async_award(1, "making the bed", "chore")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.robin_star_message").state == "+1 star for making the bed. 1 of 24."

    await coordinator.async_adjust(2, "recount", "adjust")
    await hass.async_block_till_done()
    message = hass.states.get("sensor.robin_star_message")
    assert message.state == "+1 star for making the bed. 3 of 24."
    assert message.attributes["action"] == "award"
    assert message.attributes["stars"] == 1
    assert message.attributes["reason"] == "making the bed"

    await coordinator.async_adjust(-3, "recount again", "adjust")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.robin_star_message").state == "+1 star for making the bed. 0 of 24."


async def test_a_redeem_line_refreshes_its_reward_count(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    coordinator = loaded_entry.runtime_data
    await coordinator.async_adjust(24, "seed", "adjust")
    await coordinator.async_award(1, "x", "chore")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.robin_star_message").state == "+1 star for x. 1 of 24. 1 reward ready."

    await coordinator.async_redeem("movie night")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.robin_star_message").state == "Redeemed: movie night. 0 rewards left."

    await coordinator.async_adjust(23, "seed again", "adjust")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.robin_star_message").state == "Redeemed: movie night. 1 reward left."


async def test_an_adjustment_that_fills_a_jar_shows_the_reward_ready(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
):
    coordinator = loaded_entry.runtime_data
    await coordinator.async_award(10, "chore", "chore")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.robin_star_message").state == "+10 stars for chore. 10 of 24."

    await coordinator.async_adjust(14, "seed", "adjust")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.robin_star_message").state == "+10 stars for chore. 0 of 24. 1 reward ready."


async def test_a_jar_seeded_only_by_adjustments_shows_the_count(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    coordinator = loaded_entry.runtime_data
    await coordinator.async_adjust(10, "seed", "adjust")
    await hass.async_block_till_done()
    message = hass.states.get("sensor.robin_star_message")
    assert message.state == "10 of 24."
    assert message.attributes["message"] == "10 of 24."
    assert "action" not in message.attributes

    await coordinator.async_adjust(14, "seed more", "adjust")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.robin_star_message").state == "0 of 24. 1 reward ready."


async def test_recent_is_capped_newest_first(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    for i in range(12):
        await loaded_entry.runtime_data.async_award(1, f"r{i}", "chore")
    await hass.async_block_till_done()

    recent = hass.states.get("sensor.robin_star_jar").attributes["recent"]
    assert len(recent) == 10
    assert recent[0]["reason"] == "r11"
    assert recent[-1]["reason"] == "r2"


async def test_event_names_the_jar_sensor(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    events = async_capture_events(hass, EVENT_UPDATED)

    await loaded_entry.runtime_data.async_award(1, "x", "chore")
    await hass.async_block_till_done()

    assert events[0].data["entity_id"] == "sensor.robin_star_jar"


def test_recent_and_last_event_are_excluded_from_recorder_history() -> None:
    """The recorder must not keep history of the bulky recent/last_event attributes."""
    unrecorded = StarJarSensor._unrecorded_attributes  # noqa: SLF001 - testing the attribute itself
    assert unrecorded == frozenset({"recent", "last_event"})
