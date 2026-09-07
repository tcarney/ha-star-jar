"""Tests for the optional LLM narration."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.star_jar.const import (
    CONF_AI_TASK_ENTITY,
    CONF_CHILD_NAME,
    CONF_INSTRUCTIONS,
    CONF_JAR_SIZE,
    DOMAIN,
)
from custom_components.star_jar.narration import STRUCTURE
from homeassistant.components.ai_task import GenDataTaskResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

PATCH_TARGET = "custom_components.star_jar.narration.async_generate_data"
MESSAGE = "sensor.robin_star_message"


def _result(message: str) -> GenDataTaskResult:
    return GenDataTaskResult(conversation_id="test", data={"message": message})


@pytest.fixture
def narrating_entry() -> MockConfigEntry:
    """An entry with an ai_task entity configured."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Robin",
        data={CONF_CHILD_NAME: "Robin"},
        options={CONF_JAR_SIZE: 24, CONF_AI_TASK_ENTITY: "ai_task.test", CONF_INSTRUCTIONS: "Speak like a pirate."},
        unique_id="robin",
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_no_entity_means_no_call_and_the_plain_message(hass: HomeAssistant, loaded_entry: MockConfigEntry):
    with patch(PATCH_TARGET, new_callable=AsyncMock) as generate:
        await loaded_entry.runtime_data.async_award(1, "making the bed", "chore")
        await hass.async_block_till_done(wait_background_tasks=True)

    generate.assert_not_awaited()
    message = hass.states.get(MESSAGE)
    assert message.attributes["message"] == message.state


async def test_narration_fills_the_message_attribute_only(hass: HomeAssistant, narrating_entry: MockConfigEntry):
    with patch(PATCH_TARGET, new_callable=AsyncMock, return_value=_result("Arr, a fine bed ye made!")) as generate:
        await _setup(hass, narrating_entry)
        await narrating_entry.runtime_data.async_award(1, "making the bed", "chore")
        await hass.async_block_till_done(wait_background_tasks=True)

    message = hass.states.get(MESSAGE)
    assert message.state == "+1 star for making the bed. 1 of 24."
    assert message.attributes["message"] == "Arr, a fine bed ye made!"

    generate.assert_awaited_once()
    kwargs = generate.await_args.kwargs
    assert kwargs["entity_id"] == "ai_task.test"
    assert kwargs["structure"] is STRUCTURE
    assert kwargs["instructions"].startswith("Speak like a pirate.")
    assert "- Reason: making the bed" in kwargs["instructions"]
    assert "- Jar now: 1 of 24" in kwargs["instructions"]
    assert "- Jar just filled: no" in kwargs["instructions"]


async def test_narration_survives_a_provider_error(hass: HomeAssistant, narrating_entry: MockConfigEntry):
    with patch(PATCH_TARGET, new_callable=AsyncMock, side_effect=HomeAssistantError("ollama is down")):
        await _setup(hass, narrating_entry)
        await narrating_entry.runtime_data.async_award(1, "x", "chore")
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("sensor.robin_star_jar").state == "1"
    message = hass.states.get(MESSAGE)
    assert message.attributes["message"] == message.state


async def test_narration_times_out_to_the_plain_message(hass: HomeAssistant, narrating_entry: MockConfigEntry):
    async def slow(*_args, **_kwargs) -> GenDataTaskResult:
        await asyncio.sleep(5)
        return _result("too late")

    with (
        patch(PATCH_TARGET, side_effect=slow),
        patch("custom_components.star_jar.narration.NARRATION_TIMEOUT", 0.01),
    ):
        await _setup(hass, narrating_entry)
        await narrating_entry.runtime_data.async_award(1, "x", "chore")
        await hass.async_block_till_done(wait_background_tasks=True)

    message = hass.states.get(MESSAGE)
    assert message.attributes["message"] == message.state


async def test_an_empty_answer_keeps_the_plain_message(hass: HomeAssistant, narrating_entry: MockConfigEntry):
    with patch(PATCH_TARGET, new_callable=AsyncMock, return_value=_result("   ")):
        await _setup(hass, narrating_entry)
        await narrating_entry.runtime_data.async_award(1, "x", "chore")
        await hass.async_block_till_done(wait_background_tasks=True)

    message = hass.states.get(MESSAGE)
    assert message.attributes["message"] == message.state


async def test_the_latest_narration_wins(hass: HomeAssistant, narrating_entry: MockConfigEntry):
    release = asyncio.Event()
    calls = 0
    cancelled = []

    async def generate(*_args, **_kwargs) -> GenDataTaskResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.append(True)
                raise
            return _result("stale words about the first star")
        return _result("fresh words about the second star")

    with patch(PATCH_TARGET, side_effect=generate):
        await _setup(hass, narrating_entry)
        coordinator = narrating_entry.runtime_data
        await coordinator.async_award(1, "first", "chore")
        await coordinator.async_award(1, "second", "chore")
        await hass.async_block_till_done(wait_background_tasks=True)
        assert cancelled == [True]
        assert hass.states.get(MESSAGE).attributes["message"] == "fresh words about the second star"

        release.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(MESSAGE).attributes["message"] == "fresh words about the second star"
    assert coordinator.data.narration == "fresh words about the second star"


async def test_redeem_prompt_names_the_reward(hass: HomeAssistant, narrating_entry: MockConfigEntry):
    with patch(PATCH_TARGET, new_callable=AsyncMock, return_value=_result("Enjoy the film!")) as generate:
        await _setup(hass, narrating_entry)
        coordinator = narrating_entry.runtime_data
        await coordinator.async_adjust(24, "seed", "adjust")
        await coordinator.async_redeem("movie night")
        await hass.async_block_till_done(wait_background_tasks=True)

    kwargs = generate.await_args.kwargs
    assert "- Reward redeemed: movie night" in kwargs["instructions"]
    assert "- Action: redeem" in kwargs["instructions"]
    assert hass.states.get(MESSAGE).attributes["message"] == "Enjoy the film!"


async def test_narration_is_persisted_across_a_reload(hass: HomeAssistant, narrating_entry: MockConfigEntry):
    with patch(PATCH_TARGET, new_callable=AsyncMock, return_value=_result("kept")):
        await _setup(hass, narrating_entry)
        await narrating_entry.runtime_data.async_award(1, "x", "chore")
        await hass.async_block_till_done(wait_background_tasks=True)

    await hass.config_entries.async_reload(narrating_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(MESSAGE).attributes["message"] == "kept"


async def test_adjustments_are_not_narrated(hass: HomeAssistant, narrating_entry: MockConfigEntry):
    with patch(PATCH_TARGET, new_callable=AsyncMock, return_value=_result("Nice one!")) as generate:
        await _setup(hass, narrating_entry)
        coordinator = narrating_entry.runtime_data
        await coordinator.async_award(1, "x", "chore")
        await hass.async_block_till_done(wait_background_tasks=True)
        assert hass.states.get(MESSAGE).attributes["message"] == "Nice one!"

        await coordinator.async_adjust(2, "recount", "adjust")
        await hass.async_block_till_done(wait_background_tasks=True)

    generate.assert_awaited_once()
    assert hass.states.get(MESSAGE).attributes["message"] == "+1 star for x. 3 of 24."
