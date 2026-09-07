"""Shared fixtures for star_jar tests."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.star_jar.const import (
    CONF_CHILD_NAME,
    CONF_INSTRUCTIONS,
    CONF_JAR_SIZE,
    DEFAULT_INSTRUCTIONS,
    DEFAULT_JAR_SIZE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def _custom_integrations(enable_custom_integrations: None) -> None:
    """Make custom_components/ loadable in every test."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """One child, default options, not yet added to hass."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Robin",
        data={CONF_CHILD_NAME: "Robin"},
        options={CONF_JAR_SIZE: DEFAULT_JAR_SIZE, CONF_INSTRUCTIONS: DEFAULT_INSTRUCTIONS},
        unique_id="robin",
    )


@pytest.fixture
async def loaded_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> MockConfigEntry:
    """The entry added to hass and set up."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    return mock_config_entry
