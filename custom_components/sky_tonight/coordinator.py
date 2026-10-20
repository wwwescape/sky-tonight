"""Data coordinator for Sky Tonight."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .astro import (
    Location,
    SkyEvents,
    SkyNow,
    SkyTonight,
    compute_events,
    compute_now,
    compute_tonight,
)
from .const import (
    CONF_MIN_ALTITUDE,
    DEFAULT_MIN_ALTITUDE,
    DOMAIN,
    EVENTS_REFRESH,
    TONIGHT_REFRESH,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type SkyTonightConfigEntry = ConfigEntry[SkyTonightCoordinator]


@dataclass
class SkyData:
    """A snapshot of the sky."""

    now: SkyNow
    tonight: SkyTonight
    events: SkyEvents


class SkyTonightCoordinator(DataUpdateCoordinator[SkyData]):
    """Recompute the sky on a schedule.

    Positions are refreshed every update; tonight's plan and the event
    calendar are slower to compute and change slowly, so they are cached.
    """

    config_entry: SkyTonightConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SkyTonightConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.location = Location(
            latitude=entry.data[CONF_LATITUDE],
            longitude=entry.data[CONF_LONGITUDE],
            elevation=entry.data.get(CONF_ELEVATION, 0.0),
            min_altitude=entry.options.get(CONF_MIN_ALTITUDE, DEFAULT_MIN_ALTITUDE),
        )
        self._tonight: SkyTonight | None = None
        self._events: SkyEvents | None = None

    async def _async_update_data(self) -> SkyData:
        try:
            return await self.hass.async_add_executor_job(
                self._compute, dt_util.utcnow()
            )
        except Exception as err:
            raise UpdateFailed(f"Error computing the sky: {err}") from err

    def _compute(self, now: datetime) -> SkyData:
        tonight = self._tonight
        if (
            tonight is None
            or now - tonight.computed_at >= TONIGHT_REFRESH
            or (tonight.night is not None and now >= tonight.night.end)
        ):
            tonight = self._tonight = compute_tonight(self.location, now)

        events = self._events
        if (
            events is None
            or now - events.computed_at >= EVENTS_REFRESH
            or (events.expires is not None and now >= events.expires)
        ):
            events = self._events = compute_events(
                self.location, now, dt_util.get_default_time_zone()
            )

        return SkyData(compute_now(self.location, now), tonight, events)
