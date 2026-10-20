"""Tests for the Sky Tonight config flow."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sky_tonight.const import CONF_MIN_ALTITUDE, DOMAIN

USER_INPUT = {
    CONF_NAME: "Back garden",
    CONF_LOCATION: {CONF_LATITUDE: 40.7128, CONF_LONGITUDE: -74.006},
    CONF_ELEVATION: 10,
    CONF_MIN_ALTITUDE: 15,
}


async def test_user_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Back garden"
    assert result["data"] == {
        CONF_LATITUDE: 40.7128,
        CONF_LONGITUDE: -74.006,
        CONF_ELEVATION: 10,
    }
    assert result["options"] == {CONF_MIN_ALTITUDE: 15}
    await hass.async_block_till_done()


async def test_duplicate_location(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **USER_INPUT,
            CONF_LOCATION: {CONF_LATITUDE: 51.4779, CONF_LONGITUDE: -0.0015},
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MIN_ALTITUDE: 20}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert config_entry.runtime_data.location.min_altitude == 20


async def test_reconfigure_flow(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION: {CONF_LATITUDE: 48.8566, CONF_LONGITUDE: 2.3522},
            CONF_ELEVATION: 35,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_LATITUDE] == 48.8566
    assert config_entry.unique_id == "48.8566_2.3522"
