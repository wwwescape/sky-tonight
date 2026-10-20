"""Sensors for Sky Tonight."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .astro import DARKNESS_STATES, MOON_PHASES, PLANETS
from .coordinator import SkyData, SkyTonightConfigEntry
from .entity import SkyTonightEntity

PARALLEL_UPDATES = 0

type StateType = str | int | float | datetime | None


@dataclass(frozen=True, kw_only=True)
class SkySensorDescription(SensorEntityDescription):
    """Describes a sensor for the whole sky."""

    value_fn: Callable[[SkyData], StateType]
    attrs_fn: Callable[[SkyData], dict[str, Any]] | None = None


@dataclass(frozen=True, kw_only=True)
class BodySensorDescription(SensorEntityDescription):
    """Describes a sensor repeated for each planet."""

    value_fn: Callable[[SkyData, str], StateType]


def _next_dark_sky_start(data: SkyData) -> datetime | None:
    window = data.tonight.next_dark_sky_window(data.now.computed_at)
    return window.start if window else None


def _next_dark_sky_attrs(data: SkyData) -> dict[str, Any]:
    window = data.tonight.next_dark_sky_window(data.now.computed_at)
    return {"end": window.end.isoformat() if window else None}


def _visible_planets_attrs(data: SkyData) -> dict[str, Any]:
    visible = [
        data.now.bodies[name] for name in PLANETS if data.now.bodies[name].observable
    ]
    return {"planets": [body.as_dict() for body in visible]}


def _tonight_planets_attrs(data: SkyData) -> dict[str, Any]:
    tonight = [
        data.tonight.bodies[name] for name in PLANETS if name in data.tonight.bodies
    ]
    return {
        "planets": [
            body.as_dict() for body in sorted(tonight, key=lambda b: b.visible_from)
        ]
    }


def _event_attrs(event_name: str) -> Callable[[SkyData], dict[str, Any]]:
    def attrs(data: SkyData) -> dict[str, Any]:
        event = getattr(data.events, event_name)
        if event is None:
            return {}
        return {"title": event.title, **event.details}

    return attrs


def _next_shower(data: SkyData) -> datetime | None:
    shower = data.events.next_shower(data.now.computed_at)
    return shower.peak if shower else None


def _next_shower_attrs(data: SkyData) -> dict[str, Any]:
    shower = data.events.next_shower(data.now.computed_at)
    attrs = shower.as_dict() if shower else {}
    attrs["upcoming_showers"] = [s.as_dict() for s in data.events.meteor_showers]
    return attrs


def _next_celestial(data: SkyData) -> datetime | None:
    event = data.events.next_celestial(data.now.computed_at)
    return event.time if event else None


def _next_celestial_attrs(data: SkyData) -> dict[str, Any]:
    now = data.now.computed_at
    event = data.events.next_celestial(now)
    attrs = (
        {"title": event.title, "event": event.kind, **event.details} if event else {}
    )
    attrs["upcoming"] = [e.as_dict() for e in data.events.celestial if e.time > now][
        :10
    ]
    return attrs


SKY_SENSORS: tuple[SkySensorDescription, ...] = (
    SkySensorDescription(
        key="darkness",
        translation_key="darkness",
        device_class=SensorDeviceClass.ENUM,
        options=DARKNESS_STATES,
        value_fn=lambda d: d.now.darkness,
        attrs_fn=lambda d: {
            "sun_altitude": round(d.now.sun_altitude, 1),
            "sun_azimuth": round(d.now.sun_azimuth, 1),
        },
    ),
    SkySensorDescription(
        key="astronomical_dusk",
        translation_key="astronomical_dusk",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.tonight.astronomical_dusk,
    ),
    SkySensorDescription(
        key="astronomical_dawn",
        translation_key="astronomical_dawn",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.tonight.astronomical_dawn,
    ),
    SkySensorDescription(
        key="dark_hours",
        translation_key="dark_hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        value_fn=lambda d: round(d.tonight.dark_hours, 2),
        attrs_fn=lambda d: {"windows": [w.as_dict() for w in d.tonight.dark_windows]},
    ),
    SkySensorDescription(
        key="dark_sky_hours",
        translation_key="dark_sky_hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        value_fn=lambda d: round(d.tonight.dark_sky_hours, 2),
        attrs_fn=lambda d: {
            "windows": [w.as_dict() for w in d.tonight.dark_sky_windows]
        },
    ),
    SkySensorDescription(
        key="dark_sky_start",
        translation_key="dark_sky_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_dark_sky_start,
        attrs_fn=_next_dark_sky_attrs,
    ),
    SkySensorDescription(
        key="visible_planets",
        translation_key="visible_planets",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: sum(d.now.bodies[name].observable for name in PLANETS),
        attrs_fn=_visible_planets_attrs,
    ),
    SkySensorDescription(
        key="visible_planets_tonight",
        translation_key="visible_planets_tonight",
        value_fn=lambda d: sum(name in d.tonight.bodies for name in PLANETS),
        attrs_fn=_tonight_planets_attrs,
    ),
    SkySensorDescription(
        key="moon_phase",
        translation_key="moon_phase",
        device_class=SensorDeviceClass.ENUM,
        options=MOON_PHASES,
        value_fn=lambda d: d.now.moon.phase,
        attrs_fn=lambda d: {"phase_angle": round(d.now.moon.phase_angle, 1)},
    ),
    SkySensorDescription(
        key="moon_illumination",
        translation_key="moon_illumination",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: round(d.now.moon.illumination, 1),
    ),
    SkySensorDescription(
        key="moon_altitude",
        translation_key="moon_altitude",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: round(d.now.bodies["moon"].altitude, 2),
    ),
    SkySensorDescription(
        key="moon_azimuth",
        translation_key="moon_azimuth",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda d: round(d.now.bodies["moon"].azimuth, 2),
        attrs_fn=lambda d: {"direction": d.now.bodies["moon"].direction},
    ),
    SkySensorDescription(
        key="moon_distance",
        translation_key="moon_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=lambda d: round(d.now.moon.distance_km),
    ),
    SkySensorDescription(
        key="moonrise",
        translation_key="moonrise",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.now.bodies["moon"].next_rise,
    ),
    SkySensorDescription(
        key="moonset",
        translation_key="moonset",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.now.bodies["moon"].next_set,
    ),
    SkySensorDescription(
        key="next_new_moon",
        translation_key="next_new_moon",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.now.moon.next_new_moon,
    ),
    SkySensorDescription(
        key="next_first_quarter",
        translation_key="next_first_quarter",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.now.moon.next_first_quarter,
    ),
    SkySensorDescription(
        key="next_full_moon",
        translation_key="next_full_moon",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.now.moon.next_full_moon,
    ),
    SkySensorDescription(
        key="next_last_quarter",
        translation_key="next_last_quarter",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.now.moon.next_last_quarter,
    ),
    SkySensorDescription(
        key="next_lunar_eclipse",
        translation_key="next_lunar_eclipse",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: (
            d.events.lunar_eclipse.time if d.events.lunar_eclipse else None
        ),
        attrs_fn=_event_attrs("lunar_eclipse"),
    ),
    SkySensorDescription(
        key="next_solar_eclipse",
        translation_key="next_solar_eclipse",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: (
            d.events.solar_eclipse.time if d.events.solar_eclipse else None
        ),
        attrs_fn=_event_attrs("solar_eclipse"),
    ),
    SkySensorDescription(
        key="next_meteor_shower",
        translation_key="next_meteor_shower",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_shower,
        attrs_fn=_next_shower_attrs,
    ),
    SkySensorDescription(
        key="next_celestial_event",
        translation_key="next_celestial_event",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_celestial,
        attrs_fn=_next_celestial_attrs,
    ),
)

PLANET_SENSORS: tuple[BodySensorDescription, ...] = (
    BodySensorDescription(
        key="altitude",
        translation_key="altitude",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d, b: round(d.now.bodies[b].altitude, 2),
    ),
    BodySensorDescription(
        key="azimuth",
        translation_key="azimuth",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda d, b: round(d.now.bodies[b].azimuth, 2),
    ),
    BodySensorDescription(
        key="rise",
        translation_key="rise",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d, b: d.now.bodies[b].next_rise,
    ),
    BodySensorDescription(
        key="set",
        translation_key="set",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d, b: d.now.bodies[b].next_set,
    ),
    BodySensorDescription(
        key="magnitude",
        translation_key="magnitude",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d, b: round(d.now.bodies[b].magnitude, 2),
    ),
    BodySensorDescription(
        key="constellation",
        translation_key="constellation",
        entity_registry_enabled_default=False,
        value_fn=lambda d, b: d.now.bodies[b].constellation,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkyTonightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sky Tonight sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        SkySensor(coordinator, description) for description in SKY_SENSORS
    ]
    entities += [
        PlanetSensor(coordinator, description, planet)
        for planet in PLANETS
        for description in PLANET_SENSORS
    ]
    async_add_entities(entities)


class SkySensor(SkyTonightEntity, SensorEntity):
    """A sensor for the whole sky."""

    entity_description: SkySensorDescription

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


class PlanetSensor(SkyTonightEntity, SensorEntity):
    """A sensor for one planet."""

    entity_description: BodySensorDescription

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        assert self.body is not None
        return self.entity_description.value_fn(self.coordinator.data, self.body)
