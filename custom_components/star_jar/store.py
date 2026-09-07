"""Persistent storage for one star jar."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION
from .jar import JarState


class StarJarStore:
    """Load and save a JarState under ``.storage/star_jar.<entry_id>``."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the store for a config entry."""
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")

    async def async_load(self) -> JarState:
        """Return the stored state, or a fresh one on first run."""
        raw = await self._store.async_load()
        return JarState() if raw is None else JarState.from_dict(raw)

    async def async_save(self, state: JarState) -> None:
        """Persist the whole state in one write."""
        await self._store.async_save(state.to_dict())

    async def async_remove(self) -> None:
        """Delete the storage file. Used when the config entry is removed."""
        await self._store.async_remove()
