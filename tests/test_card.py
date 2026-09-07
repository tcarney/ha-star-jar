"""Tests for the bundled Lovelace card."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.star_jar.const import CARD_URL_PATH
from homeassistant.components.lovelace.const import CONF_RESOURCE_TYPE_WS, DOMAIN as LOVELACE_DOMAIN
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


def _card_resources(hass: HomeAssistant) -> list[str]:
    return [
        item[CONF_URL]
        for item in hass.data[LOVELACE_DOMAIN].resources.async_items()
        if item[CONF_URL].startswith(CARD_URL_PATH)
    ]


async def test_card_is_served(hass: HomeAssistant, loaded_entry: MockConfigEntry, hass_client: ClientSessionGenerator):
    client = await hass_client()

    response = await client.get(CARD_URL_PATH)

    assert response.status == 200
    assert 'customElements.define("star-jar-card"' in await response.text()


async def test_card_is_registered_as_a_lovelace_resource(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    urls = _card_resources(hass)

    assert len(urls) == 1
    assert urls[0].startswith(f"{CARD_URL_PATH}?v=")


async def test_a_stale_resource_is_updated_in_place(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    """A resource left by an older build keeps its id and gets the current cache-busting query."""
    assert await async_setup_component(hass, LOVELACE_DOMAIN, {})
    resources = hass.data[LOVELACE_DOMAIN].resources
    await resources.async_load()
    resources.loaded = True
    stale = await resources.async_create_item({CONF_RESOURCE_TYPE_WS: "module", CONF_URL: f"{CARD_URL_PATH}?v=0"})

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    urls = _card_resources(hass)
    assert len(urls) == 1
    assert urls[0] != f"{CARD_URL_PATH}?v=0"
    assert resources.data[stale["id"]][CONF_URL] == urls[0]
