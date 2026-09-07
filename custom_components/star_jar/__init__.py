"""The Star Jar integration: a reward ledger for one child, driven by services."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http.server import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import CARD_JS, CARD_URL_PATH, DOMAIN, LOGGER, PLATFORMS
from .coordinator import StarJarCoordinator
from .jar import roll_day
from .services import async_register_services
from .store import StarJarStore

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type StarJarConfigEntry = ConfigEntry[StarJarCoordinator]


async def _async_register_card_resource(hass: HomeAssistant, resource_url: str) -> None:
    """Register the card as a Lovelace resource, the way chore_calendar does.

    Lovelace loads its resources before any card renders. `add_extra_js_url`
    only adds a fire-and-forget import to the page, which races the first
    render and shows "custom element doesn't exist" until a reload, so it is
    the fallback, used only when the resource collection is YAML-managed or
    lovelace is not loaded. A resource already registered for an older build
    of the file is updated in place so the cache-busting query stays current.
    """
    from homeassistant.components.lovelace.const import (  # noqa: PLC0415 - deferred, lovelace is only an after_dependency
        CONF_RESOURCE_TYPE_WS,
        DOMAIN as LOVELACE_DOMAIN,
    )
    from homeassistant.components.lovelace.resources import (  # noqa: PLC0415 - deferred, lovelace is only an after_dependency
        ResourceStorageCollection,
        ResourceYAMLCollection,
    )

    lovelace_data = hass.data.get(LOVELACE_DOMAIN)
    if not lovelace_data or not lovelace_data.resources:
        LOGGER.debug("Lovelace not available, falling back to add_extra_js_url")
        add_extra_js_url(hass, resource_url)
        return

    resources: ResourceStorageCollection | ResourceYAMLCollection = lovelace_data.resources
    if not resources.loaded and isinstance(resources, ResourceStorageCollection):
        await resources.async_load()
        resources.loaded = True

    for item in resources.async_items():
        item_url: str = item.get(CONF_URL, "")
        if not item_url.startswith(CARD_URL_PATH):
            continue
        if item_url == resource_url:
            LOGGER.debug("Card resource already registered")
            return
        if isinstance(resources, ResourceStorageCollection):
            await resources.async_update_item(item[CONF_ID], {CONF_URL: resource_url})
            LOGGER.debug("Updated card resource to %s", resource_url)
        return

    if isinstance(resources, ResourceYAMLCollection):
        LOGGER.debug("Lovelace resources are YAML-managed, falling back to add_extra_js_url")
        add_extra_js_url(hass, resource_url)
        return

    data = await resources.async_create_item({CONF_RESOURCE_TYPE_WS: "module", CONF_URL: resource_url})
    LOGGER.debug("Registered card as Lovelace resource %s", data[CONF_ID])


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services and the card. Both live at integration level, not per entry."""
    await async_register_services(hass)

    # The file's mtime is the cache-busting key, so a HACS update (which
    # rewrites the file) is enough for browsers to fetch the new build.
    card_path = Path(__file__).parent / "www" / CARD_JS
    await hass.http.async_register_static_paths(
        [StaticPathConfig(url_path=CARD_URL_PATH, path=str(card_path), cache_headers=True)]
    )
    await _async_register_card_resource(hass, f"{CARD_URL_PATH}?v={int(card_path.stat().st_mtime)}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: StarJarConfigEntry) -> bool:
    """Load one jar from storage, catch up a missed midnight, and expose it."""
    store = StarJarStore(hass, entry.entry_id)
    loaded = await store.async_load()
    state = roll_day(loaded, dt_util.now().date())
    if state is not loaded:
        await store.async_save(state)

    coordinator = StarJarCoordinator(hass, entry, store, state)
    entry.runtime_data = coordinator
    entry.async_on_unload(async_track_time_change(hass, coordinator.async_handle_midnight, hour=0, minute=0, second=0))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: StarJarConfigEntry) -> bool:
    """Unload a jar."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: StarJarConfigEntry) -> None:
    """Delete the jar's storage when the entry is removed."""
    await StarJarStore(hass, entry.entry_id).async_remove()
