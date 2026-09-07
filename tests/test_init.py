"""Tests for setup, unload and removal."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.star_jar.coordinator import StarJarCoordinator
from custom_components.star_jar.jar import JarState
from custom_components.star_jar.store import StarJarStore
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_creates_a_coordinator_with_fresh_state(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    coordinator = loaded_entry.runtime_data

    assert isinstance(coordinator, StarJarCoordinator)
    assert coordinator.data.jar == 0
    assert coordinator.data.rewards_available == 0
    assert coordinator.jar_size == 24


async def test_setup_loads_persisted_state(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    await StarJarStore(hass, mock_config_entry.entry_id).async_save(JarState(jar=9, rewards_available=1))

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.data.jar == 9
    assert mock_config_entry.runtime_data.data.rewards_available == 1


async def test_unload(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    assert await hass.config_entries.async_unload(loaded_entry.entry_id)
    await hass.async_block_till_done()

    assert loaded_entry.state is ConfigEntryState.NOT_LOADED


async def test_remove_deletes_storage(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    await loaded_entry.runtime_data.async_award(1, "x", "chore")
    entry_id = loaded_entry.entry_id

    await hass.config_entries.async_remove(entry_id)
    await hass.async_block_till_done()

    assert await StarJarStore(hass, entry_id).async_load() == JarState()
