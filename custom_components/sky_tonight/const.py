"""Constants for Sky Tonight."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "sky_tonight"
DEFAULT_NAME: Final = "Sky Tonight"

CONF_MIN_ALTITUDE: Final = "min_altitude"
DEFAULT_MIN_ALTITUDE: Final = 10.0

UPDATE_INTERVAL: Final = timedelta(minutes=5)
TONIGHT_REFRESH: Final = timedelta(minutes=30)
EVENTS_REFRESH: Final = timedelta(hours=6)
