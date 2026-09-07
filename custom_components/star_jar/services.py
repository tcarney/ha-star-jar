"""The three services, the only writers of the jar."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import (
    ATTR_REASON,
    ATTR_REWARD,
    ATTR_SOURCE,
    ATTR_STARS,
    DEFAULT_ADJUST_SOURCE,
    DOMAIN,
    MAX_ADJUST,
    MAX_STARS_PER_AWARD,
    SERVICE_ADJUST,
    SERVICE_AWARD,
    SERVICE_REDEEM,
)
from .coordinator import StarJarCoordinator
from .jar import JarEmptyError

# The 200-character cap keeps `plain_message` under Home Assistant's 255-character state limit.
_TEXT = vol.All(cv.string, str.strip, vol.Length(min=1, max=200))

SERVICE_AWARD_SCHEMA = vol.Schema(
    {
        **cv.ENTITY_SERVICE_FIELDS,
        vol.Optional(ATTR_STARS, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_STARS_PER_AWARD)),
        vol.Required(ATTR_REASON): _TEXT,
        vol.Required(ATTR_SOURCE): _TEXT,
    }
)

SERVICE_ADJUST_SCHEMA = vol.Schema(
    {
        **cv.ENTITY_SERVICE_FIELDS,
        vol.Required(ATTR_STARS): vol.All(vol.Coerce(int), vol.Range(min=-MAX_ADJUST, max=MAX_ADJUST), vol.NotIn([0])),
        vol.Required(ATTR_REASON): _TEXT,
        vol.Optional(ATTR_SOURCE, default=DEFAULT_ADJUST_SOURCE): _TEXT,
    }
)

SERVICE_REDEEM_SCHEMA = vol.Schema(
    {
        **cv.ENTITY_SERVICE_FIELDS,
        vol.Required(ATTR_REWARD): _TEXT,
    }
)


async def _async_targeted_jars(call: ServiceCall) -> list[StarJarCoordinator]:
    """Resolve the call's target (device, entity or area) to loaded star jars."""
    jars: list[StarJarCoordinator] = []
    for entry_id in await async_extract_config_entry_ids(call):
        entry = call.hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == DOMAIN and entry.state is ConfigEntryState.LOADED:
            jars.append(entry.runtime_data)
    if not jars:
        msg = "No star jar was targeted. Target the jar device or one of its sensors."
        raise ServiceValidationError(msg)
    return jars


async def _async_handle_award(call: ServiceCall) -> None:
    """Grant stars."""
    for coordinator in await _async_targeted_jars(call):
        await coordinator.async_award(call.data[ATTR_STARS], call.data[ATTR_REASON], call.data[ATTR_SOURCE])


async def _async_handle_adjust(call: ServiceCall) -> None:
    """Reconcile by a signed delta."""
    for coordinator in await _async_targeted_jars(call):
        await coordinator.async_adjust(call.data[ATTR_STARS], call.data[ATTR_REASON], call.data[ATTR_SOURCE])


async def _async_handle_redeem(call: ServiceCall) -> None:
    """Spend one reward."""
    for coordinator in await _async_targeted_jars(call):
        try:
            await coordinator.async_redeem(call.data[ATTR_REWARD])
        except JarEmptyError as err:
            msg = f"{coordinator.entry.title} has no reward to redeem."
            raise ServiceValidationError(msg) from err


async def async_register_services(hass: HomeAssistant) -> None:
    """Register the services once, at integration setup."""
    hass.services.async_register(DOMAIN, SERVICE_AWARD, _async_handle_award, schema=SERVICE_AWARD_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ADJUST, _async_handle_adjust, schema=SERVICE_ADJUST_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_REDEEM, _async_handle_redeem, schema=SERVICE_REDEEM_SCHEMA)
