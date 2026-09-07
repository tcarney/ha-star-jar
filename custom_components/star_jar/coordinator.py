"""One coordinator per jar: the only place state changes."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import jar
from .const import (
    ATTR_ACTION,
    ATTR_JAR,
    ATTR_JAR_BEFORE,
    ATTR_JAR_FILLED,
    ATTR_REASON,
    ATTR_REWARD,
    ATTR_REWARDS_AVAILABLE,
    ATTR_SOURCE,
    ATTR_STARS,
    ATTR_STARS_TODAY,
    CONF_JAR_SIZE,
    DEFAULT_JAR_SIZE,
    DOMAIN,
    EVENT_UPDATED,
    LOGGER,
)
from .jar import JarState, LedgerEntry, Transition
from .narration import Narrator
from .store import StarJarStore

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

type Mutation = Callable[[JarState, datetime], Transition]


class StarJarCoordinator(DataUpdateCoordinator[JarState]):
    """Hold the jar state, persist every change atomically, and publish it.

    There is no polling: ``update_interval`` is None and the data only moves
    through :meth:`_async_apply`, which holds a lock so two service calls
    arriving together cannot read the same state and lose a star.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, store: StarJarStore, state: JarState) -> None:
        """Initialize with the state already loaded from storage."""
        super().__init__(hass, LOGGER, config_entry=entry, name=f"{DOMAIN}.{entry.entry_id}", update_interval=None)
        self.entry = entry
        self.store = store
        self._lock = asyncio.Lock()
        self._seq = 0
        self._narration_task: asyncio.Task[None] | None = None
        self.narrator = Narrator(hass, self)
        self.async_set_updated_data(state)

    @property
    def jar_size(self) -> int:
        """Stars needed to fill the jar, from options."""
        return int(self.entry.options.get(CONF_JAR_SIZE, DEFAULT_JAR_SIZE))

    async def async_award(self, stars: int, reason: str, source: str) -> LedgerEntry:
        """Grant stars."""
        return await self._async_apply(lambda state, now: jar.award(state, stars, reason, source, now, self.jar_size))

    async def async_adjust(self, stars: int, reason: str, source: str) -> LedgerEntry:
        """Reconcile by a signed delta."""
        return await self._async_apply(lambda state, now: jar.adjust(state, stars, reason, source, now, self.jar_size))

    async def async_redeem(self, reward: str) -> LedgerEntry:
        """Spend one reward. Raises JarEmptyError when none is available."""
        return await self._async_apply(lambda state, now: jar.redeem(state, reward, now))

    async def async_handle_midnight(self, now: datetime) -> None:
        """Start a new day. Today's count goes to zero; the jar and the ledger do not move."""
        async with self._lock:
            state = jar.roll_day(self.data, now.date())
            if state is self.data:
                return
            await self.store.async_save(state)
            self.async_set_updated_data(state)

    async def async_set_narration(self, seq: int, text: str) -> None:
        """Attach narration to the state it describes. Dropped if a newer mutation has happened since."""
        async with self._lock:
            if seq != self._seq:
                LOGGER.debug("%s: dropping narration for a superseded event", self.entry.title)
                return
            state = replace(self.data, narration=text)
            await self.store.async_save(state)
            self.async_set_updated_data(state)

    async def _async_apply(self, mutate: Mutation) -> LedgerEntry:
        """Roll the day, apply the mutation, persist, publish, fire the event, then narrate in the background."""
        async with self._lock:
            now = dt_util.now()
            transition = mutate(jar.roll_day(self.data, now.date()), now)
            await self.store.async_save(transition.state)
            self.async_set_updated_data(transition.state)
            self._seq += 1
            seq = self._seq
            if self._narration_task is not None and not self._narration_task.done():
                self._narration_task.cancel()
        self._fire_event(transition)
        self._narration_task = self.entry.async_create_background_task(
            self.hass, self.narrator.async_narrate(transition, seq), name=f"{DOMAIN} narration"
        )
        return transition.entry

    def _fire_event(self, transition: Transition) -> None:
        """Fire ``star_jar_updated`` for this transition."""
        entry, state = transition.entry, transition.state
        registry = er.async_get(self.hass)
        payload = {
            "entity_id": registry.async_get_entity_id("sensor", DOMAIN, f"{self.entry.entry_id}_star_jar"),
            ATTR_ACTION: str(entry.action),
            ATTR_STARS: entry.stars,
            ATTR_REASON: entry.reason,
            ATTR_SOURCE: entry.source,
            ATTR_REWARD: entry.reward,
            ATTR_JAR_BEFORE: entry.jar_before,
            ATTR_JAR: state.jar,
            ATTR_JAR_FILLED: entry.jar_filled,
            ATTR_REWARDS_AVAILABLE: state.rewards_available,
            ATTR_STARS_TODAY: state.stars_today,
        }
        self.hass.bus.async_fire(EVENT_UPDATED, payload)
        LOGGER.debug("%s: %s", self.entry.title, payload)
