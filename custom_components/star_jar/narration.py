"""Messages for the child.

``plain_message`` is deterministic and always available: it is the message
sensor's state and the fallback for its ``message`` attribute. ``Narrator``
optionally asks an ``ai_task`` entity for flavour text and attaches it to the
state it describes. It runs off the critical path, it is asked for one text
field and never a number, and if anything goes wrong the plain message stands.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.ai_task import async_generate_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    CONF_AI_TASK_ENTITY,
    CONF_INSTRUCTIONS,
    DEFAULT_INSTRUCTIONS,
    DOMAIN,
    LOGGER,
    NARRATION_TIMEOUT,
    JarAction,
)
from .jar import JarState, LedgerEntry, Transition

if TYPE_CHECKING:
    from .coordinator import StarJarCoordinator

STRUCTURE = vol.Schema(
    {vol.Required("message", description="One short sentence addressed to the child."): selector.TextSelector()}
)


def _count(number: int, noun: str) -> str:
    """Pluralize a count: ``1 reward``, ``2 rewards``."""
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def plain_message(entry: LedgerEntry, state: JarState, jar_size: int) -> str:
    """One deterministic line describing an award or redeem entry, with the current counts."""
    if entry.action is JarAction.REDEEM:
        return f"Redeemed: {entry.reward}. {_count(state.rewards_available, 'reward')} left."
    head = f"{entry.stars:+d} {'star' if abs(entry.stars) == 1 else 'stars'} for {entry.reason}."
    ready = f" {_count(state.rewards_available, 'reward')} ready." if state.rewards_available else ""
    if entry.jar_filled:
        return f"{head} Jar full!{ready}"
    return f"{head} {state.jar} of {jar_size}.{ready}"


def count_message(state: JarState, jar_size: int) -> str:
    """The count alone, for a jar with no award or redeem to describe."""
    line = f"{state.jar} of {jar_size}."
    if state.rewards_available:
        line += f" {_count(state.rewards_available, 'reward')} ready."
    return line


def build_prompt(entry: LedgerEntry, state: JarState, jar_size: int, instructions: str) -> str:
    """The persona text followed by the exact facts of the transition."""
    facts = [
        f"Action: {entry.action}",
        f"Stars: {entry.stars:+d}",
        f"Reason: {entry.reason}",
        f"Source: {entry.source}",
        f"Jar before: {entry.jar_before} of {jar_size}",
        f"Jar now: {state.jar} of {jar_size}",
        f"Stars to fill: {jar_size - state.jar}",
        f"Jar just filled: {'yes' if entry.jar_filled else 'no'}",
        f"Rewards available: {state.rewards_available}",
        f"Stars today: {state.stars_today}",
    ]
    if entry.reward:
        facts.append(f"Reward redeemed: {entry.reward}")
    return f"{instructions.strip()}\n\nFacts:\n" + "\n".join(f"- {fact}" for fact in facts)


class Narrator:
    """Turn a transition into flavour text, when an ai_task entity is configured."""

    def __init__(self, hass: HomeAssistant, coordinator: StarJarCoordinator) -> None:
        """Bind to the jar whose events are narrated."""
        self._hass = hass
        self._coordinator = coordinator

    async def async_narrate(self, transition: Transition, seq: int) -> None:
        """Generate text for the transition and hand it to the coordinator, tagged with its sequence."""
        if transition.entry.action is JarAction.ADJUST:
            # Adjustments are bookkeeping, never narrated.
            return
        options = self._coordinator.entry.options
        entity_id = options.get(CONF_AI_TASK_ENTITY)
        if not entity_id:
            return
        instructions = options.get(CONF_INSTRUCTIONS) or DEFAULT_INSTRUCTIONS
        prompt = build_prompt(transition.entry, transition.state, self._coordinator.jar_size, instructions)
        text = await self._async_generate(entity_id, prompt)
        if text:
            await self._coordinator.async_set_narration(seq, text)

    async def _async_generate(self, entity_id: str, prompt: str) -> str | None:
        """Ask the model. Any failure, including a timeout, means no narration rather than an error."""
        try:
            async with asyncio.timeout(NARRATION_TIMEOUT):
                result = await async_generate_data(
                    self._hass,
                    task_name=f"{DOMAIN} narration",
                    entity_id=entity_id,
                    instructions=prompt,
                    structure=STRUCTURE,
                )
        except Exception as err:  # noqa: BLE001 - narration must never fail an award, whatever the provider raises
            LOGGER.warning("Narration failed, keeping the plain message: %s", err)
            return None
        data = result.data if isinstance(result.data, dict) else {}
        message = str(data.get("message", "")).strip()
        return message or None
