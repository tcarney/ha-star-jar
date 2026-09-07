"""Tests for the award, adjust and redeem services."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.star_jar.const import (
    ATTR_REASON,
    ATTR_REWARD,
    ATTR_SOURCE,
    ATTR_STARS,
    DOMAIN,
    SERVICE_ADJUST,
    SERVICE_AWARD,
    SERVICE_REDEEM,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr


def _device_id(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    return device.id


async def test_award_targets_the_device(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    await hass.services.async_call(
        DOMAIN,
        SERVICE_AWARD,
        {"device_id": _device_id(hass, loaded_entry), ATTR_REASON: "made bed", ATTR_SOURCE: "chore"},
        blocking=True,
    )

    assert hass.states.get("sensor.robin_star_jar").state == "1"
    assert loaded_entry.runtime_data.data.last_entry.source == "chore"


async def test_award_accepts_any_of_the_jar_sensors_as_target(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    await hass.services.async_call(
        DOMAIN,
        SERVICE_AWARD,
        {"entity_id": "sensor.robin_rewards_redeemed", ATTR_STARS: 3, ATTR_REASON: "x", ATTR_SOURCE: "bonus"},
        blocking=True,
    )

    assert hass.states.get("sensor.robin_star_jar").state == "3"


async def test_adjust_defaults_its_source_and_floors_at_zero(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    device_id = _device_id(hass, loaded_entry)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_AWARD,
        {"device_id": device_id, ATTR_STARS: 2, ATTR_REASON: "x", ATTR_SOURCE: "chore"},
        blocking=True,
    )

    await hass.services.async_call(
        DOMAIN, SERVICE_ADJUST, {"device_id": device_id, ATTR_STARS: -5, ATTR_REASON: "recount"}, blocking=True
    )

    assert hass.states.get("sensor.robin_star_jar").state == "0"
    assert loaded_entry.runtime_data.data.last_entry.source == "adjust"


async def test_redeem_refuses_at_zero_then_works_once_a_jar_is_full(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    device_id = _device_id(hass, loaded_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_REDEEM, {"device_id": device_id, ATTR_REWARD: "movie night"}, blocking=True
        )
    assert hass.states.get("sensor.robin_rewards_redeemed").state == "0"

    await hass.services.async_call(
        DOMAIN, SERVICE_ADJUST, {"device_id": device_id, ATTR_STARS: 24, ATTR_REASON: "seed"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, SERVICE_REDEEM, {"device_id": device_id, ATTR_REWARD: "movie night"}, blocking=True
    )

    assert hass.states.get("sensor.robin_rewards_available").state == "0"
    assert hass.states.get("sensor.robin_rewards_redeemed").state == "1"


@pytest.mark.parametrize(
    ("service", "data"),
    [
        (SERVICE_AWARD, {ATTR_STARS: 0, ATTR_REASON: "x", ATTR_SOURCE: "chore"}),
        (SERVICE_AWARD, {ATTR_STARS: 11, ATTR_REASON: "x", ATTR_SOURCE: "chore"}),
        (SERVICE_AWARD, {ATTR_REASON: "", ATTR_SOURCE: "chore"}),
        (SERVICE_AWARD, {ATTR_REASON: "x"}),
        (SERVICE_AWARD, {ATTR_REASON: "   ", ATTR_SOURCE: "chore"}),
        (SERVICE_ADJUST, {ATTR_STARS: 0, ATTR_REASON: "x"}),
        (SERVICE_ADJUST, {ATTR_REASON: "x"}),
        (SERVICE_ADJUST, {ATTR_STARS: 101, ATTR_REASON: "x"}),
        (SERVICE_REDEEM, {ATTR_REWARD: ""}),
        (SERVICE_REDEEM, {}),
    ],
)
async def test_invalid_fields_are_rejected_before_anything_changes(
    hass: HomeAssistant, loaded_entry: MockConfigEntry, service: str, data: dict
):
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, service, {"device_id": _device_id(hass, loaded_entry), **data}, blocking=True
        )

    assert loaded_entry.runtime_data.data.ledger == ()


async def test_a_call_without_a_jar_target_is_an_error(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, SERVICE_AWARD, {ATTR_REASON: "x", ATTR_SOURCE: "chore"}, blocking=True)


async def test_an_unloaded_jar_is_not_a_target(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    device_id = _device_id(hass, loaded_entry)
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_AWARD, {"device_id": device_id, ATTR_REASON: "x", ATTR_SOURCE: "chore"}, blocking=True
        )
