"""Tests for setting up Sky Tonight and its entities."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sky_tonight.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_setup_and_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    darkness = hass.states.get("sensor.sky_tonight_darkness")
    assert darkness is not None
    assert darkness.state in {
        "day",
        "civil_twilight",
        "nautical_twilight",
        "astronomical_twilight",
        "night",
    }
    assert "sun_altitude" in darkness.attributes

    jupiter = hass.states.get("binary_sensor.sky_tonight_jupiter_visible")
    assert jupiter is not None
    assert jupiter.state in {"on", "off"}
    assert {"altitude", "azimuth", "magnitude", "optics", "visible_tonight"} <= set(
        jupiter.attributes
    )

    assert hass.states.get("sensor.sky_tonight_mars_altitude") is not None
    assert hass.states.get("sensor.sky_tonight_moon_phase") is not None
    assert hass.states.get("sensor.sky_tonight_next_full_moon") is not None
    assert hass.states.get("sensor.sky_tonight_visible_planets_tonight") is not None
    assert hass.states.get("sensor.sky_tonight_next_meteor_shower") is not None
    assert hass.states.get("binary_sensor.sky_tonight_dark_sky") is not None

    # Noisier entities are registered but disabled by default.
    azimuth = entity_registry.async_get("sensor.sky_tonight_mars_azimuth")
    assert azimuth is not None
    assert azimuth.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get("sensor.sky_tonight_mars_azimuth") is None


async def test_diagnostics(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diagnostics["location"]["latitude"] == "**REDACTED**"
    assert diagnostics["data"]["now"]["bodies"]["mars"]["altitude"] is not None
