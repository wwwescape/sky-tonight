"""Fixtures for Sky Tonight tests."""

from __future__ import annotations

from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sky_tonight.const import CONF_MIN_ALTITUDE, DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations in every test."""


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry for Greenwich."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Sky Tonight",
        unique_id="51.4779_-0.0015",
        data={CONF_LATITUDE: 51.4779, CONF_LONGITUDE: -0.0015, CONF_ELEVATION: 46},
        options={CONF_MIN_ALTITUDE: 10},
    )
