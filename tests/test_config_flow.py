"""Tests for the config flow."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.star_jar.const import (
    CONF_AI_TASK_ENTITY,
    CONF_CHILD_NAME,
    CONF_INSTRUCTIONS,
    CONF_JAR_SIZE,
    DEFAULT_INSTRUCTIONS,
    DEFAULT_JAR_SIZE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_step_creates_an_entry_with_default_options(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CHILD_NAME: " Robin "})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Robin"
    assert result["data"] == {CONF_CHILD_NAME: "Robin"}
    assert result["options"] == {CONF_JAR_SIZE: DEFAULT_JAR_SIZE, CONF_INSTRUCTIONS: DEFAULT_INSTRUCTIONS}


async def test_user_step_rejects_a_blank_name(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CHILD_NAME: "   "})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_CHILD_NAME: "invalid_name"}


async def test_duplicate_name_aborts(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CHILD_NAME: "robin"})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_updates_options_and_reloads(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_JAR_SIZE: 12, CONF_AI_TASK_ENTITY: "ai_task.test", CONF_INSTRUCTIONS: "Be brief."},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert loaded_entry.options == {
        CONF_JAR_SIZE: 12,
        CONF_AI_TASK_ENTITY: "ai_task.test",
        CONF_INSTRUCTIONS: "Be brief.",
    }
    assert loaded_entry.runtime_data.jar_size == 12


async def test_options_flow_can_clear_the_narration_entity(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    hass.config_entries.async_update_entry(
        loaded_entry, options={**loaded_entry.options, CONF_AI_TASK_ENTITY: "ai_task.test"}
    )

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_JAR_SIZE: 24, CONF_INSTRUCTIONS: DEFAULT_INSTRUCTIONS}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_AI_TASK_ENTITY not in loaded_entry.options


async def test_a_smaller_jar_size_applies_at_the_next_award(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    await loaded_entry.runtime_data.async_award(5, "x", "chore")

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_JAR_SIZE: 3, CONF_INSTRUCTIONS: DEFAULT_INSTRUCTIONS}
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.robin_star_jar").state == "5"
    assert hass.states.get("sensor.robin_rewards_available").state == "0"
    assert hass.states.get("sensor.robin_star_jar").attributes["stars_to_fill"] == 0

    await loaded_entry.runtime_data.async_award(1, "y", "chore")
    await hass.async_block_till_done()

    assert hass.states.get("sensor.robin_star_jar").state == "0"
    assert hass.states.get("sensor.robin_rewards_available").state == "2"
