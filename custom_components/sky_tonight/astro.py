"""Astronomy calculations for Sky Tonight.

This module is deliberately free of Home Assistant imports so it can be
tested on its own. Every function takes an aware datetime and returns aware
UTC datetimes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, tzinfo
import math
from typing import Any

import astronomy as ae

PLANETS: tuple[str, ...] = (
    "mercury",
    "venus",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
)

BODIES: dict[str, ae.Body] = {
    "sun": ae.Body.Sun,
    "moon": ae.Body.Moon,
    "mercury": ae.Body.Mercury,
    "venus": ae.Body.Venus,
    "mars": ae.Body.Mars,
    "jupiter": ae.Body.Jupiter,
    "saturn": ae.Body.Saturn,
    "uranus": ae.Body.Uranus,
    "neptune": ae.Body.Neptune,
}

# Altitude of the Sun's centre at sunrise and sunset, allowing for refraction
# and the Sun's semi-diameter.
SUNSET_ALTITUDE = -0.833
CIVIL_TWILIGHT = -6.0
NAUTICAL_TWILIGHT = -12.0
ASTRONOMICAL_TWILIGHT = -18.0

DARKNESS_DAY = "day"
DARKNESS_CIVIL = "civil_twilight"
DARKNESS_NAUTICAL = "nautical_twilight"
DARKNESS_ASTRONOMICAL = "astronomical_twilight"
DARKNESS_NIGHT = "night"
DARKNESS_STATES = [
    DARKNESS_DAY,
    DARKNESS_CIVIL,
    DARKNESS_NAUTICAL,
    DARKNESS_ASTRONOMICAL,
    DARKNESS_NIGHT,
]

OPTICS_NAKED_EYE = "naked_eye"
OPTICS_BINOCULARS = "binoculars"
OPTICS_TELESCOPE = "telescope"

MOON_PHASES = [
    "new_moon",
    "waxing_crescent",
    "first_quarter",
    "waxing_gibbous",
    "full_moon",
    "waning_gibbous",
    "last_quarter",
    "waning_crescent",
]

# Principal phases (new, quarters, full) are reported while the Moon's
# ecliptic phase angle is within this many degrees of them, which is roughly
# half a day either side.
PRINCIPAL_PHASE_TOLERANCE = 6.0

# Below this illuminated fraction the Moon is lost in the Sun's glare.
MIN_MOON_FRACTION = 0.01

SUPERMOON_DISTANCE_KM = 360_000

COMPASS_POINTS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]  # fmt: skip

TONIGHT_STEP = timedelta(minutes=5)
EVENT_HORIZON_DAYS = 548  # about 18 months, matching the card
MAX_UPCOMING_EVENTS = 10
METEOR_UPCOMING_DAYS = 60


@dataclass(frozen=True)
class Location:
    """Observer location."""

    latitude: float
    longitude: float
    elevation: float = 0.0
    min_altitude: float = 10.0

    @property
    def observer(self) -> ae.Observer:
        """Return an Astronomy Engine observer."""
        return ae.Observer(self.latitude, self.longitude, self.elevation)


# ---------------------------------------------------------------------------
# Time helpers


def to_time(value: datetime) -> ae.Time:
    """Convert an aware datetime to an Astronomy Engine time."""
    utc = value.astimezone(UTC)
    return ae.Time.Make(
        utc.year,
        utc.month,
        utc.day,
        utc.hour,
        utc.minute,
        utc.second + utc.microsecond / 1_000_000,
    )


def from_time(value: ae.Time) -> datetime:
    """Convert an Astronomy Engine time to an aware UTC datetime."""
    return value.Utc().replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


# ---------------------------------------------------------------------------
# Positions


@dataclass
class Position:
    """Where a body is in the observer's sky."""

    altitude: float
    azimuth: float
    ra: float
    dec: float


def position(body: ae.Body, when: ae.Time, observer: ae.Observer) -> Position:
    """Return a body's apparent altitude and azimuth, with refraction."""
    equ = ae.Equator(body, when, observer, True, True)
    hor = ae.Horizon(when, observer, equ.ra, equ.dec, ae.Refraction.Normal)
    return Position(hor.altitude, hor.azimuth, equ.ra, equ.dec)


def sun_altitude(when: ae.Time, observer: ae.Observer) -> float:
    """Return the Sun's apparent altitude."""
    return position(ae.Body.Sun, when, observer).altitude


def compass_direction(azimuth: float) -> str:
    """Return the 16-point compass direction for an azimuth."""
    return COMPASS_POINTS[int((azimuth % 360) / 22.5 + 0.5) % 16]


def darkness_state(sun_alt: float) -> str:
    """Classify the sky by how far the Sun is below the horizon."""
    if sun_alt > SUNSET_ALTITUDE:
        return DARKNESS_DAY
    if sun_alt > CIVIL_TWILIGHT:
        return DARKNESS_CIVIL
    if sun_alt > NAUTICAL_TWILIGHT:
        return DARKNESS_NAUTICAL
    if sun_alt > ASTRONOMICAL_TWILIGHT:
        return DARKNESS_ASTRONOMICAL
    return DARKNESS_NIGHT


def required_sun_altitude(magnitude: float) -> float:
    """Return how low the Sun must be before an object this bright shows.

    Venus and a bright Jupiter pop out early in civil twilight; Uranus and
    Neptune need a properly dark sky.
    """
    if magnitude <= -3.0:
        return -3.0
    if magnitude <= 0.5:
        return CIVIL_TWILIGHT
    if magnitude <= 3.0:
        return -9.0
    if magnitude <= 5.0:
        return NAUTICAL_TWILIGHT
    return -15.0


def optics_for(magnitude: float) -> str:
    """Return the least equipment needed to see an object this bright."""
    if magnitude <= 5.0:
        return OPTICS_NAKED_EYE
    if magnitude <= 9.0:
        return OPTICS_BINOCULARS
    return OPTICS_TELESCOPE


def moon_phase_name(phase_angle: float) -> str:
    """Name the Moon's phase from its ecliptic phase angle (0 = new)."""
    angle = phase_angle % 360
    for index, principal in enumerate((0.0, 90.0, 180.0, 270.0, 360.0)):
        if abs(angle - principal) <= PRINCIPAL_PHASE_TOLERANCE:
            return MOON_PHASES[(index * 2) % 8]
    return MOON_PHASES[int(angle // 90) * 2 + 1]


def is_observable(
    name: str,
    altitude: float,
    sun_alt: float,
    magnitude: float,
    moon_fraction: float,
    min_altitude: float,
) -> bool:
    """Return whether a body can realistically be seen right now."""
    if altitude < min_altitude:
        return False
    if name == "moon":
        # The Moon is often visible in daylight; only a near-new Moon hides.
        return moon_fraction >= MIN_MOON_FRACTION
    return sun_alt <= required_sun_altitude(magnitude)


def next_rise_set(
    body: ae.Body, observer: ae.Observer, when: ae.Time
) -> tuple[datetime | None, datetime | None]:
    """Return the next rise and set after a time, if any within two days."""
    rise = ae.SearchRiseSet(body, observer, ae.Direction.Rise, when, 2)
    set_ = ae.SearchRiseSet(body, observer, ae.Direction.Set, when, 2)
    return (
        from_time(rise) if rise else None,
        from_time(set_) if set_ else None,
    )


# ---------------------------------------------------------------------------
# Current state


@dataclass
class BodyNow:
    """A body's current state."""

    name: str
    altitude: float
    azimuth: float
    direction: str
    magnitude: float
    constellation: str
    optics: str
    observable: bool
    next_rise: datetime | None
    next_set: datetime | None
    distance_km: float

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON friendly representation."""
        return {
            "name": self.name,
            "altitude": round(self.altitude, 1),
            "azimuth": round(self.azimuth, 1),
            "direction": self.direction,
            "magnitude": round(self.magnitude, 1),
            "constellation": self.constellation,
            "optics": self.optics,
            "visible": self.observable,
            "next_rise": _iso(self.next_rise),
            "next_set": _iso(self.next_set),
        }


@dataclass
class MoonNow:
    """The Moon's phase details."""

    phase: str
    phase_angle: float
    illumination: float
    distance_km: float
    next_new_moon: datetime | None
    next_first_quarter: datetime | None
    next_full_moon: datetime | None
    next_last_quarter: datetime | None


@dataclass
class SkyNow:
    """Everything that changes minute to minute."""

    computed_at: datetime
    sun_altitude: float
    sun_azimuth: float
    darkness: str
    bodies: dict[str, BodyNow]
    moon: MoonNow


def _moon_quarters(when: ae.Time) -> dict[int, datetime]:
    quarters: dict[int, datetime] = {}
    quarter = ae.SearchMoonQuarter(when)
    while len(quarters) < 4:
        quarters.setdefault(quarter.quarter, from_time(quarter.time))
        quarter = ae.NextMoonQuarter(quarter)
    return quarters


def compute_now(location: Location, now: datetime) -> SkyNow:
    """Compute where everything is right now."""
    observer = location.observer
    when = to_time(now)

    sun = position(ae.Body.Sun, when, observer)
    moon_illum = ae.Illumination(ae.Body.Moon, when)

    bodies: dict[str, BodyNow] = {}
    for name, body in BODIES.items():
        if name == "sun":
            continue
        pos = position(body, when, observer)
        illum = ae.Illumination(body, when)
        j2000 = ae.Equator(body, when, observer, False, True)
        rise, set_ = next_rise_set(body, observer, when)
        bodies[name] = BodyNow(
            name=name,
            altitude=pos.altitude,
            azimuth=pos.azimuth,
            direction=compass_direction(pos.azimuth),
            magnitude=illum.mag,
            constellation=ae.Constellation(j2000.ra, j2000.dec).name,
            optics=optics_for(illum.mag),
            observable=is_observable(
                name,
                pos.altitude,
                sun.altitude,
                illum.mag,
                moon_illum.phase_fraction,
                location.min_altitude,
            ),
            next_rise=rise,
            next_set=set_,
            distance_km=illum.geo_dist * ae.KM_PER_AU,
        )

    phase_angle = ae.MoonPhase(when)
    quarters = _moon_quarters(when)
    moon = MoonNow(
        phase=moon_phase_name(phase_angle),
        phase_angle=phase_angle,
        illumination=moon_illum.phase_fraction * 100,
        distance_km=ae.GeoMoon(when).Length() * ae.KM_PER_AU,
        next_new_moon=quarters.get(0),
        next_first_quarter=quarters.get(1),
        next_full_moon=quarters.get(2),
        next_last_quarter=quarters.get(3),
    )

    return SkyNow(
        computed_at=now,
        sun_altitude=sun.altitude,
        sun_azimuth=sun.azimuth,
        darkness=darkness_state(sun.altitude),
        bodies=bodies,
        moon=moon,
    )


# ---------------------------------------------------------------------------
# Tonight


@dataclass
class Window:
    """A span of time."""

    start: datetime
    end: datetime

    @property
    def hours(self) -> float:
        """Return the length in hours."""
        return (self.end - self.start).total_seconds() / 3600

    def contains(self, when: datetime) -> bool:
        """Return whether a time falls inside the window."""
        return self.start <= when < self.end

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON friendly representation."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "hours": round(self.hours, 2),
        }


@dataclass
class BodyTonight:
    """When a body can be seen tonight."""

    name: str
    visible_from: datetime
    visible_until: datetime
    best_time: datetime
    max_altitude: float
    magnitude: float
    optics: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON friendly representation."""
        return {
            "name": self.name,
            "visible_from": self.visible_from.isoformat(),
            "visible_until": self.visible_until.isoformat(),
            "best_time": self.best_time.isoformat(),
            "max_altitude": round(self.max_altitude, 1),
            "magnitude": round(self.magnitude, 1),
            "optics": self.optics,
        }


@dataclass
class SkyTonight:
    """The coming (or current) night."""

    computed_at: datetime
    night: Window | None
    astronomical_dusk: datetime | None
    astronomical_dawn: datetime | None
    dark_windows: list[Window] = field(default_factory=list)
    dark_sky_windows: list[Window] = field(default_factory=list)
    bodies: dict[str, BodyTonight] = field(default_factory=dict)

    @property
    def dark_hours(self) -> float:
        """Return the hours of astronomical darkness."""
        return sum(window.hours for window in self.dark_windows)

    @property
    def dark_sky_hours(self) -> float:
        """Return the hours of astronomical darkness with no Moon up."""
        return sum(window.hours for window in self.dark_sky_windows)

    def next_dark_sky_window(self, now: datetime) -> Window | None:
        """Return the current or next moonless dark window."""
        return next((w for w in self.dark_sky_windows if w.end > now), None)


def night_window(location: Location, now: datetime) -> Window | None:
    """Return the night in progress, or the next one.

    A night runs from sunset to sunrise. During polar night the next 24 hours
    are used; during polar day there is no night and None is returned.
    """
    observer = location.observer
    when = to_time(now)

    if sun_altitude(when, observer) <= SUNSET_ALTITUDE:
        sunset = ae.SearchRiseSet(ae.Body.Sun, observer, ae.Direction.Set, when, -2)
        sunrise = ae.SearchRiseSet(ae.Body.Sun, observer, ae.Direction.Rise, when, 2)
        start = from_time(sunset) if sunset else now
        end = from_time(sunrise) if sunrise else now + timedelta(days=1)
        return Window(start, end)

    sunset = ae.SearchRiseSet(ae.Body.Sun, observer, ae.Direction.Set, when, 2)
    if sunset is None:
        return None
    sunrise = ae.SearchRiseSet(ae.Body.Sun, observer, ae.Direction.Rise, sunset, 2)
    end = from_time(sunrise) if sunrise else from_time(sunset) + timedelta(days=1)
    return Window(from_time(sunset), end)


def _merge(samples: list[tuple[datetime, bool]], step: timedelta) -> list[Window]:
    windows: list[Window] = []
    start: datetime | None = None
    for when, flag in samples:
        if flag and start is None:
            start = when
        elif not flag and start is not None:
            windows.append(Window(start, when))
            start = None
    if start is not None:
        windows.append(Window(start, samples[-1][0] + step))
    return windows


def compute_tonight(location: Location, now: datetime) -> SkyTonight:
    """Work out what tonight holds: darkness, moonlight and planets."""
    observer = location.observer
    night = night_window(location, now)
    tonight = SkyTonight(
        computed_at=now, night=night, astronomical_dusk=None, astronomical_dawn=None
    )
    if night is None:
        return tonight

    start_time = to_time(night.start)
    span_days = (night.end - night.start).total_seconds() / 86400
    dusk = ae.SearchAltitude(
        ae.Body.Sun, observer, ae.Direction.Set, start_time, span_days,
        ASTRONOMICAL_TWILIGHT,
    )  # fmt: skip
    dawn = ae.SearchAltitude(
        ae.Body.Sun, observer, ae.Direction.Rise, dusk or start_time, span_days,
        ASTRONOMICAL_TWILIGHT,
    )  # fmt: skip
    if dusk and dawn and from_time(dawn) <= night.end:
        tonight.astronomical_dusk = from_time(dusk)
        tonight.astronomical_dawn = from_time(dawn)

    mid = to_time(night.start + (night.end - night.start) / 2)
    magnitudes = {name: ae.Illumination(BODIES[name], mid).mag for name in PLANETS}
    moon_fraction = ae.Illumination(ae.Body.Moon, mid).phase_fraction

    dark: list[tuple[datetime, bool]] = []
    dark_sky: list[tuple[datetime, bool]] = []
    best: dict[str, dict[str, Any]] = {}

    # Sample on whole five-minute marks so reported times read cleanly.
    step_seconds = TONIGHT_STEP.total_seconds()
    when_dt = datetime.fromtimestamp(
        math.ceil(night.start.timestamp() / step_seconds) * step_seconds, UTC
    )
    while when_dt < night.end:
        when = to_time(when_dt)
        sun_alt = sun_altitude(when, observer)
        moon_alt = position(ae.Body.Moon, when, observer).altitude
        is_dark = sun_alt <= ASTRONOMICAL_TWILIGHT
        dark.append((when_dt, is_dark))
        dark_sky.append((when_dt, is_dark and moon_alt < 0))

        for name in (*PLANETS, "moon"):
            alt = (
                moon_alt
                if name == "moon"
                else position(BODIES[name], when, observer).altitude
            )
            magnitude = magnitudes.get(name, -12.0)
            if not is_observable(
                name, alt, sun_alt, magnitude, moon_fraction, location.min_altitude
            ):
                continue
            entry = best.setdefault(
                name, {"from": when_dt, "best": when_dt, "alt": alt}
            )
            entry["until"] = when_dt + TONIGHT_STEP
            if alt > entry["alt"]:
                entry["alt"] = alt
                entry["best"] = when_dt
        when_dt += TONIGHT_STEP

    tonight.dark_windows = _merge(dark, TONIGHT_STEP)
    tonight.dark_sky_windows = _merge(dark_sky, TONIGHT_STEP)
    for name, entry in best.items():
        magnitude = (
            ae.Illumination(ae.Body.Moon, mid).mag
            if name == "moon"
            else magnitudes[name]
        )
        tonight.bodies[name] = BodyTonight(
            name=name,
            visible_from=entry["from"],
            visible_until=min(entry["until"], night.end),
            best_time=entry["best"],
            max_altitude=entry["alt"],
            magnitude=magnitude,
            optics=optics_for(magnitude),
        )
    return tonight


# ---------------------------------------------------------------------------
# Events


@dataclass
class Event:
    """A dated astronomical event."""

    kind: str
    time: datetime
    title: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON friendly representation."""
        return {
            "kind": self.kind,
            "time": self.time.isoformat(),
            "title": self.title,
            **self.details,
        }


@dataclass(frozen=True)
class MeteorShower:
    """A major annual meteor shower."""

    name: str
    start: tuple[int, int]
    end: tuple[int, int]
    peak: tuple[int, int]
    zhr: int
    ra: float  # J2000 radiant, sidereal hours
    dec: float  # J2000 radiant, degrees


# Approximate active windows, peak dates, and zenith hourly rates (ZHR) per
# commonly published figures (e.g. the IMO calendar). Peak dates drift by a
# day or two year to year; this is a static table, the same as the card's.
METEOR_SHOWERS: tuple[MeteorShower, ...] = (
    MeteorShower("Quadrantids", (12, 28), (1, 12), (1, 3), 120, 15.33, 49.5),
    MeteorShower("Lyrids", (4, 16), (4, 25), (4, 22), 18, 18.17, 33.3),
    MeteorShower("Eta Aquariids", (4, 19), (5, 28), (5, 5), 50, 22.5, -1.0),
    MeteorShower("Alpha Capricornids", (7, 3), (8, 15), (7, 30), 5, 20.47, -10.0),
    MeteorShower("Southern Delta Aquariids", (7, 12), (8, 23), (7, 30), 25, 22.6, -16.0),
    MeteorShower("Perseids", (7, 17), (8, 24), (8, 12), 100, 3.22, 58.0),
    MeteorShower("Draconids", (10, 6), (10, 10), (10, 8), 10, 17.47, 54.0),
    MeteorShower("Southern Taurids", (9, 10), (11, 20), (11, 5), 5, 3.53, 13.0),
    MeteorShower("Orionids", (10, 2), (11, 7), (10, 21), 20, 6.35, 16.0),
    MeteorShower("Northern Taurids", (10, 20), (12, 10), (11, 12), 5, 3.87, 22.0),
    MeteorShower("Leonids", (11, 6), (11, 30), (11, 17), 15, 10.28, 22.0),
    MeteorShower("Geminids", (12, 4), (12, 17), (12, 14), 150, 7.55, 32.5),
    MeteorShower("Ursids", (12, 17), (12, 26), (12, 22), 10, 14.47, 75.8),
)  # fmt: skip


@dataclass
class ShowerInfo:
    """A meteor shower occurrence for this location."""

    name: str
    zhr: int
    active: bool
    active_start: date
    active_end: date
    peak_night: date
    best_time: datetime | None
    radiant_altitude: float
    moon_illumination: float
    midnight: datetime

    @property
    def peak(self) -> datetime:
        """Return the best viewing time, or local midnight of the peak night."""
        return self.best_time or self.midnight

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON friendly representation."""
        return {
            "name": self.name,
            "zhr": self.zhr,
            "active": self.active,
            "active_start": self.active_start.isoformat(),
            "active_end": self.active_end.isoformat(),
            "peak_night": self.peak_night.isoformat(),
            "best_time": _iso(self.best_time),
            "radiant_altitude": round(self.radiant_altitude, 1),
            "moon_illumination": round(self.moon_illumination),
        }


def _shower_cycle(shower: MeteorShower, year: int) -> tuple[date, date, date]:
    start = date(year, *shower.start)
    end = date(year, *shower.end)
    peak = date(year, *shower.peak)
    if end < start:
        end = end.replace(year=year + 1)
    if peak < start:
        peak = peak.replace(year=year + 1)
    return start, end, peak


def _shower_best_time(
    shower: MeteorShower, location: Location, night: date, tz: tzinfo
) -> tuple[datetime | None, float]:
    """Find when the radiant is highest in a dark sky on a given night.

    The radiant's J2000 position is used directly; precession over a few
    decades is far smaller than the uncertainty in the radiant itself.
    """
    observer = location.observer
    when_dt = datetime.combine(night, datetime.min.time(), tz) + timedelta(hours=16)
    end = when_dt + timedelta(hours=16)
    best_time: datetime | None = None
    best_alt = -90.0
    while when_dt < end:
        when = to_time(when_dt)
        if sun_altitude(when, observer) <= NAUTICAL_TWILIGHT:
            hor = ae.Horizon(
                when, observer, shower.ra, shower.dec, ae.Refraction.Normal
            )
            if hor.altitude > best_alt:
                best_alt = hor.altitude
                best_time = when_dt.astimezone(UTC)
        when_dt += timedelta(minutes=10)
    return best_time, best_alt


def meteor_showers(location: Location, now: datetime, tz: tzinfo) -> list[ShowerInfo]:
    """Return showers that are active, or peak within the next 60 days."""
    today = now.astimezone(tz).date()
    results: list[ShowerInfo] = []
    for shower in METEOR_SHOWERS:
        cycles = [_shower_cycle(shower, today.year + d) for d in (-1, 0, 1)]
        active = next((c for c in cycles if c[0] <= today <= c[1]), None)
        if active:
            cycle = active
        else:
            upcoming = [c for c in cycles if c[2] >= today]
            if not upcoming:
                continue
            cycle = min(upcoming, key=lambda c: c[2])
            if (cycle[2] - today).days > METEOR_UPCOMING_DAYS:
                continue
        start, end, peak = cycle
        # The peak date is the night the shower peaks, so look from that
        # evening into the following morning.
        peak_night = peak - timedelta(days=1)
        best_time, radiant_alt = _shower_best_time(shower, location, peak_night, tz)
        midnight = datetime.combine(peak, datetime.min.time(), tz).astimezone(UTC)
        moon_time = to_time(best_time or midnight)
        results.append(
            ShowerInfo(
                name=shower.name,
                zhr=shower.zhr,
                active=active is not None,
                active_start=start,
                active_end=end,
                peak_night=peak_night,
                best_time=best_time if radiant_alt > 0 else None,
                radiant_altitude=radiant_alt,
                moon_illumination=ae.Illumination(
                    ae.Body.Moon, moon_time
                ).phase_fraction
                * 100,
                midnight=midnight,
            )
        )
    return sorted(results, key=lambda s: s.peak_night)


def _eclipse_kind(kind: ae.EclipseKind) -> str:
    return kind.name.lower()


def next_lunar_eclipse(location: Location, now: datetime) -> Event | None:
    """Return the next lunar eclipse the Moon is up for, here."""
    observer = location.observer
    # Start a few hours back so an eclipse already under way is found.
    eclipse = ae.SearchLunarEclipse(to_time(now - timedelta(hours=4)))
    for _ in range(12):
        peak = from_time(eclipse.peak)
        begin = peak - timedelta(minutes=eclipse.sd_penum)
        end = peak + timedelta(minutes=eclipse.sd_penum)
        if peak > now + timedelta(days=EVENT_HORIZON_DAYS):
            return None
        if end > now:
            samples = [begin + (end - begin) * i / 8 for i in range(9)]
            altitudes = [
                position(ae.Body.Moon, to_time(t), observer).altitude for t in samples
            ]
            if max(altitudes) > 0:
                details: dict[str, Any] = {
                    "eclipse_kind": _eclipse_kind(eclipse.kind),
                    "obscuration": round(eclipse.obscuration * 100, 1),
                    "begin": begin.isoformat(),
                    "end": end.isoformat(),
                    "moon_altitude_at_peak": round(
                        position(ae.Body.Moon, eclipse.peak, observer).altitude, 1
                    ),
                    "in_progress": begin <= now <= end,
                }
                if eclipse.sd_partial > 0:
                    details["partial_begin"] = (
                        peak - timedelta(minutes=eclipse.sd_partial)
                    ).isoformat()
                    details["partial_end"] = (
                        peak + timedelta(minutes=eclipse.sd_partial)
                    ).isoformat()
                if eclipse.sd_total > 0:
                    details["total_begin"] = (
                        peak - timedelta(minutes=eclipse.sd_total)
                    ).isoformat()
                    details["total_end"] = (
                        peak + timedelta(minutes=eclipse.sd_total)
                    ).isoformat()
                return Event(
                    "lunar_eclipse",
                    peak,
                    f"{_eclipse_kind(eclipse.kind).title()} lunar eclipse",
                    details,
                )
        eclipse = ae.NextLunarEclipse(eclipse.peak)
    return None


def next_solar_eclipse(location: Location, now: datetime) -> Event | None:
    """Return the next solar eclipse visible from this location."""
    observer = location.observer
    eclipse = ae.SearchLocalSolarEclipse(to_time(now - timedelta(hours=4)), observer)
    for _ in range(12):
        peak = from_time(eclipse.peak.time)
        begin = from_time(eclipse.partial_begin.time)
        end = from_time(eclipse.partial_end.time)
        if peak > now + timedelta(days=EVENT_HORIZON_DAYS):
            return None
        if end > now:
            details: dict[str, Any] = {
                "eclipse_kind": _eclipse_kind(eclipse.kind),
                "obscuration": round(eclipse.obscuration * 100, 1),
                "begin": begin.isoformat(),
                "end": end.isoformat(),
                "sun_altitude_at_peak": round(eclipse.peak.altitude, 1),
                "in_progress": begin <= now <= end,
            }
            if eclipse.total_begin and eclipse.total_end:
                details["total_begin"] = from_time(eclipse.total_begin.time).isoformat()
                details["total_end"] = from_time(eclipse.total_end.time).isoformat()
            return Event(
                "solar_eclipse",
                peak,
                f"{_eclipse_kind(eclipse.kind).title()} solar eclipse",
                details,
            )
        eclipse = ae.NextLocalSolarEclipse(eclipse.peak.time, observer)
    return None


def celestial_events(now: datetime) -> list[Event]:
    """Return upcoming seasons, oppositions, elongations and supermoons."""
    horizon = now + timedelta(days=EVENT_HORIZON_DAYS)
    start = to_time(now)
    events: list[Event] = []

    for year in (now.year, now.year + 1):
        seasons = ae.Seasons(year)
        for kind, title, when in (
            ("equinox", "March equinox", seasons.mar_equinox),
            ("solstice", "June solstice", seasons.jun_solstice),
            ("equinox", "September equinox", seasons.sep_equinox),
            ("solstice", "December solstice", seasons.dec_solstice),
        ):
            events.append(Event(kind, from_time(when), title))

    for name in ("mars", "jupiter", "saturn", "uranus", "neptune"):
        when = ae.SearchRelativeLongitude(BODIES[name], 0, start)
        mag = ae.Illumination(BODIES[name], when).mag
        events.append(
            Event(
                "opposition",
                from_time(when),
                f"{name.title()} at opposition",
                {"body": name, "magnitude": round(mag, 1)},
            )
        )

    for name in ("mercury", "venus"):
        cursor = start
        for _ in range(4):
            elongation = ae.SearchMaxElongation(BODIES[name], cursor)
            if elongation is None:
                break
            visibility = elongation.visibility.name.lower()
            events.append(
                Event(
                    "greatest_elongation",
                    from_time(elongation.time),
                    f"{name.title()} at greatest {visibility} elongation",
                    {
                        "body": name,
                        "visibility": visibility,
                        "elongation": round(elongation.elongation, 1),
                    },
                )
            )
            cursor = elongation.time.AddDays(1)

    cursor = start
    for _ in range(20):
        full = ae.SearchMoonPhase(180, cursor, 40)
        if full is None or from_time(full) > horizon:
            break
        distance = ae.GeoMoon(full).Length() * ae.KM_PER_AU
        if distance < SUPERMOON_DISTANCE_KM:
            events.append(
                Event(
                    "supermoon",
                    from_time(full),
                    "Supermoon",
                    {"distance_km": round(distance)},
                )
            )
        cursor = full.AddDays(1)

    return sorted((e for e in events if now < e.time <= horizon), key=lambda e: e.time)


@dataclass
class SkyEvents:
    """Events that change on the scale of days."""

    computed_at: datetime
    lunar_eclipse: Event | None
    solar_eclipse: Event | None
    meteor_showers: list[ShowerInfo]
    celestial: list[Event]

    @property
    def active_showers(self) -> list[ShowerInfo]:
        """Return showers active today."""
        return [s for s in self.meteor_showers if s.active]

    def next_shower(self, now: datetime) -> ShowerInfo | None:
        """Return the shower with the soonest peak that has not passed."""
        upcoming = [s for s in self.meteor_showers if s.peak > now]
        return min(upcoming, key=lambda s: s.peak) if upcoming else None

    def next_celestial(self, now: datetime) -> Event | None:
        """Return the next celestial event that has not passed."""
        return next((e for e in self.celestial if e.time > now), None)

    @property
    def expires(self) -> datetime | None:
        """Return the earliest upcoming event time, after which to refresh."""
        times = [e.time for e in (self.lunar_eclipse, self.solar_eclipse) if e]
        times += [s.peak for s in self.meteor_showers]
        times += [e.time for e in self.celestial[:1]]
        upcoming = [t for t in times if t > self.computed_at]
        return min(upcoming) if upcoming else None


def compute_events(location: Location, now: datetime, tz: tzinfo) -> SkyEvents:
    """Compute upcoming eclipses, meteor showers and celestial events."""
    return SkyEvents(
        computed_at=now,
        lunar_eclipse=next_lunar_eclipse(location, now),
        solar_eclipse=next_solar_eclipse(location, now),
        meteor_showers=meteor_showers(location, now, tz),
        celestial=celestial_events(now),
    )
