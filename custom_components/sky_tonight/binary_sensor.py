"""Binary sensors for Sky Tonight."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .astro import DARKNESS_NIGHT, PLANETS
from .coordinator import SkyData, SkyTonightConfigEntry
from .entity import SkyTonightEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SkyBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a binary sensor for the whole sky."""

    is_on_fn: Callable[[SkyData], bool]
    attrs_fn: Callable[[SkyData], dict[str, Any]] | None = None


def _is_dark_sky(data: SkyData) -> bool:
    return data.now.darkness == DARKNESS_NIGHT and data.now.bodies["moon"].altitude < 0


def _dark_sky_attrs(data: SkyData) -> dict[str, Any]:
    window = data.tonight.next_dark_sky_window(data.now.computed_at)
    return {
        "next_start": window.start.isoformat() if window else None,
        "next_end": window.end.isoformat() if window else None,
    }


SKY_BINARY_SENSORS: tuple[SkyBinarySensorDescription, ...] = (
    SkyBinarySensorDescription(
        key="dark_sky",
        translation_key="dark_sky",
        is_on_fn=_is_dark_sky,
        attrs_fn=_dark_sky_attrs,
    ),
    SkyBinarySensorDescription(
        key="meteor_shower_active",
        translation_key="meteor_shower_active",
        is_on_fn=lambda d: bool(d.events.active_showers),
        attrs_fn=lambda d: {
            "active_showers": [s.as_dict() for s in d.events.active_showers]
        },
    ),
)

VISIBLE_DESCRIPTION = BinarySensorEntityDescription(
    key="visible",
    translation_key="visible",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkyTonightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sky Tonight binary sensors."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [
        SkyBinarySensor(coordinator, description) for description in SKY_BINARY_SENSORS
    ]
    entities += [
        BodyVisibleBinarySensor(coordinator, VISIBLE_DESCRIPTION, body)
        for body in ("moon", *PLANETS)
    ]
    async_add_entities(entities)


class SkyBinarySensor(SkyTonightEntity, BinarySensorEntity):
    """A binary sensor for the whole sky."""

    entity_description: SkyBinarySensorDescription

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


class BodyVisibleBinarySensor(SkyTonightEntity, BinarySensorEntity):
    """Whether a body can be seen right now.

    On when the body is above the minimum altitude and the sky is dark enough
    for something of its brightness.
    """

    @property
    def is_on(self) -> bool:
        """Return the state."""
        assert self.body is not None
        return self.coordinator.data.now.bodies[self.body].observable

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the body's position and tonight's viewing window."""
        assert self.body is not None
        data = self.coordinator.data
        attrs = data.now.bodies[self.body].as_dict()
        attrs.pop("name")
        attrs.pop("visible")
        tonight = data.tonight.bodies.get(self.body)
        attrs["visible_tonight"] = tonight is not None
        if tonight is not None:
            attrs["visible_from"] = tonight.visible_from.isoformat()
            attrs["visible_until"] = tonight.visible_until.isoformat()
            attrs["best_time"] = tonight.best_time.isoformat()
            attrs["max_altitude"] = round(tonight.max_altitude, 1)
        return attrs
