"""Sensor platform for Star Jar: five read-only views of one JarState."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ACTION,
    ATTR_AT,
    ATTR_JAR_SIZE,
    ATTR_LAST_EVENT,
    ATTR_MESSAGE,
    ATTR_REASON,
    ATTR_RECENT,
    ATTR_REWARD,
    ATTR_SOURCE,
    ATTR_STARS,
    ATTR_STARS_TO_FILL,
    DOMAIN,
    RECENT_LIMIT,
)
from .coordinator import StarJarCoordinator
from .jar import JarState
from .narration import count_message, plain_message

if TYPE_CHECKING:
    from . import StarJarConfigEntry

NO_STARS_YET = "No stars yet."


@dataclass(frozen=True, kw_only=True)
class StarJarSensorDescription(SensorEntityDescription):
    """A sensor is a function of the jar state and the jar size."""

    value_fn: Callable[[JarState, int], StateType]
    attributes_fn: Callable[[JarState, int], dict[str, Any]] | None = None


def _jar_attributes(state: JarState, jar_size: int) -> dict[str, Any]:
    """Progress and history for the jar sensor."""
    last = state.last_entry
    return {
        ATTR_JAR_SIZE: jar_size,
        ATTR_STARS_TO_FILL: max(0, jar_size - state.jar),
        ATTR_LAST_EVENT: last.to_dict() if last else None,
        ATTR_RECENT: [entry.to_dict() for entry in reversed(state.ledger[-RECENT_LIMIT:])],
    }


def _message_state(state: JarState, jar_size: int) -> str:
    """The deterministic line: the latest award or redeem, a bare count, or a placeholder."""
    if (entry := state.last_message_entry) is not None:
        return plain_message(entry, state, jar_size)
    return count_message(state, jar_size) if state.ledger else NO_STARS_YET


def _message_attributes(state: JarState, jar_size: int) -> dict[str, Any]:
    """The narration if there is one, else the plain line, plus what the latest award or redeem describes."""
    attributes: dict[str, Any] = {ATTR_MESSAGE: state.narration or _message_state(state, jar_size)}
    if (entry := state.last_message_entry) is not None:
        attributes.update(
            {
                ATTR_ACTION: str(entry.action),
                ATTR_STARS: entry.stars,
                ATTR_REASON: entry.reason,
                ATTR_SOURCE: entry.source,
                ATTR_REWARD: entry.reward,
                ATTR_AT: entry.at.isoformat(),
            }
        )
    return attributes


SENSORS: tuple[StarJarSensorDescription, ...] = (
    StarJarSensorDescription(
        key="star_jar",
        translation_key="star_jar",
        icon="mdi:star",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state, _: state.jar,
        attributes_fn=_jar_attributes,
    ),
    StarJarSensorDescription(
        key="stars_today",
        translation_key="stars_today",
        icon="mdi:star-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state, _: state.stars_today,
    ),
    StarJarSensorDescription(
        key="rewards_available",
        translation_key="rewards_available",
        icon="mdi:gift",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state, _: state.rewards_available,
    ),
    StarJarSensorDescription(
        key="rewards_redeemed",
        translation_key="rewards_redeemed",
        icon="mdi:trophy",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda state, _: state.rewards_redeemed,
    ),
    StarJarSensorDescription(
        key="star_message",
        translation_key="star_message",
        icon="mdi:message-text",
        value_fn=_message_state,
        attributes_fn=_message_attributes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: StarJarConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the five sensors for this jar."""
    coordinator = entry.runtime_data
    async_add_entities(StarJarSensor(coordinator, description) for description in SENSORS)


class StarJarSensor(CoordinatorEntity[StarJarCoordinator], SensorEntity):
    """One read-only view of the jar."""

    entity_description: StarJarSensorDescription
    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({ATTR_RECENT, ATTR_LAST_EVENT})

    def __init__(self, coordinator: StarJarCoordinator, description: StarJarSensorDescription) -> None:
        """Attach to the jar's device."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> StateType:
        """The value for this view."""
        return self.entity_description.value_fn(self.coordinator.data, self.coordinator.jar_size)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The attributes for this view, if it has any."""
        if (attributes_fn := self.entity_description.attributes_fn) is None:
            return None
        return attributes_fn(self.coordinator.data, self.coordinator.jar_size)
