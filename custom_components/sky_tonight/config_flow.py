"""Config flow for Sky Tonight."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    UnitOfLength,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)
import voluptuous as vol

from .const import CONF_MIN_ALTITUDE, DEFAULT_MIN_ALTITUDE, DEFAULT_NAME, DOMAIN
from .coordinator import SkyTonightConfigEntry

ELEVATION_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=-500,
        max=9000,
        step=1,
        mode=NumberSelectorMode.BOX,
        unit_of_measurement=UnitOfLength.METERS,
    )
)
MIN_ALTITUDE_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=0,
        max=45,
        step=1,
        mode=NumberSelectorMode.SLIDER,
        unit_of_measurement="°",
    )
)


def _location_schema(
    latitude: float, longitude: float, elevation: float
) -> dict[vol.Marker, Any]:
    return {
        vol.Required(
            CONF_LOCATION,
            default={CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude},
        ): LocationSelector(),
        vol.Required(CONF_ELEVATION, default=elevation): ELEVATION_SELECTOR,
    }


def _location_data(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_LATITUDE: user_input[CONF_LOCATION][CONF_LATITUDE],
        CONF_LONGITUDE: user_input[CONF_LOCATION][CONF_LONGITUDE],
        CONF_ELEVATION: user_input[CONF_ELEVATION],
    }


def _unique_id(data: dict[str, Any]) -> str:
    return f"{data[CONF_LATITUDE]:.4f}_{data[CONF_LONGITUDE]:.4f}"


class SkyTonightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sky Tonight."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SkyTonightConfigEntry,
    ) -> SkyTonightOptionsFlow:
        """Return the options flow."""
        return SkyTonightOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a location."""
        if user_input is not None:
            data = _location_data(user_input)
            await self.async_set_unique_id(_unique_id(data))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=data,
                options={CONF_MIN_ALTITUDE: user_input[CONF_MIN_ALTITUDE]},
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
                **_location_schema(
                    self.hass.config.latitude,
                    self.hass.config.longitude,
                    self.hass.config.elevation,
                ),
                vol.Required(
                    CONF_MIN_ALTITUDE, default=DEFAULT_MIN_ALTITUDE
                ): MIN_ALTITUDE_SELECTOR,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Move an existing location."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            data = _location_data(user_input)
            unique_id = _unique_id(data)
            if unique_id != entry.unique_id:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
            return self.async_update_reload_and_abort(
                entry, unique_id=unique_id, data=data
            )

        schema = vol.Schema(
            _location_schema(
                entry.data[CONF_LATITUDE],
                entry.data[CONF_LONGITUDE],
                entry.data.get(CONF_ELEVATION, 0),
            )
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema)


class SkyTonightOptionsFlow(OptionsFlowWithReload):
    """Handle options for Sky Tonight."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MIN_ALTITUDE,
                    default=self.config_entry.options.get(
                        CONF_MIN_ALTITUDE, DEFAULT_MIN_ALTITUDE
                    ),
                ): MIN_ALTITUDE_SELECTOR,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
