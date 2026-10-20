"""Diagnostics for Sky Tonight."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .coordinator import SkyTonightConfigEntry

TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SkyTonightConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "location": async_redact_data(asdict(coordinator.location), TO_REDACT),
        "data": asdict(coordinator.data) if coordinator.data else None,
    }
