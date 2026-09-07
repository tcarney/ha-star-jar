"""Tests for StarJarStore."""

from __future__ import annotations

from datetime import UTC, date, datetime

from custom_components.star_jar.jar import JarState, award
from custom_components.star_jar.store import StarJarStore
from homeassistant.core import HomeAssistant

NOW = datetime(2026, 9, 7, 18, 30, tzinfo=UTC)


async def test_load_from_empty_store_gives_a_fresh_state(hass: HomeAssistant):
    store = StarJarStore(hass, "entry1")

    assert await store.async_load() == JarState()


async def test_save_then_load_round_trips(hass: HomeAssistant):
    state = award(JarState(today=date(2026, 9, 7)), 3, "x", "chore", NOW, 24).state
    await StarJarStore(hass, "entry1").async_save(state)

    assert await StarJarStore(hass, "entry1").async_load() == state


async def test_stores_are_keyed_by_entry(hass: HomeAssistant):
    await StarJarStore(hass, "entry1").async_save(JarState(jar=5))

    assert await StarJarStore(hass, "entry2").async_load() == JarState()


async def test_remove_forgets_everything(hass: HomeAssistant):
    store = StarJarStore(hass, "entry1")
    await store.async_save(JarState(jar=5))
    await store.async_remove()

    assert await StarJarStore(hass, "entry1").async_load() == JarState()
