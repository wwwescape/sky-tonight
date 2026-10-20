"""Tests for the astronomy calculations, against known events."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.sky_tonight import astro

LONDON = astro.Location(51.4779, -0.0015, 46, min_altitude=10)
NEW_YORK = astro.Location(40.7128, -74.0060, 10)
DALLAS = astro.Location(32.7767, -96.7970, 140)
TROMSO = astro.Location(69.6492, 18.9553, 10)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


@pytest.mark.parametrize(
    ("angle", "phase"),
    [
        (0, "new_moon"),
        (359, "new_moon"),
        (30, "waxing_crescent"),
        (90, "first_quarter"),
        (120, "waxing_gibbous"),
        (183, "full_moon"),
        (200, "waning_gibbous"),
        (268, "last_quarter"),
        (300, "waning_crescent"),
    ],
)
def test_moon_phase_name(angle: float, phase: str) -> None:
    assert astro.moon_phase_name(angle) == phase


@pytest.mark.parametrize(
    ("azimuth", "direction"),
    [(0, "N"), (11, "N"), (12, "NNE"), (90, "E"), (225, "SW"), (355, "N")],
)
def test_compass_direction(azimuth: float, direction: str) -> None:
    assert astro.compass_direction(azimuth) == direction


@pytest.mark.parametrize(
    ("sun_alt", "state"),
    [
        (10, "day"),
        (-0.5, "day"),
        (-3, "civil_twilight"),
        (-9, "nautical_twilight"),
        (-15, "astronomical_twilight"),
        (-30, "night"),
    ],
)
def test_darkness_state(sun_alt: float, state: str) -> None:
    assert astro.darkness_state(sun_alt) == state


def test_optics() -> None:
    assert astro.optics_for(-4.4) == "naked_eye"
    assert astro.optics_for(5.7) == "binoculars"
    assert astro.optics_for(7.8) == "binoculars"
    assert astro.optics_for(13.0) == "telescope"


def test_bright_planets_show_in_brighter_twilight() -> None:
    # Venus in civil twilight, but not Uranus.
    assert astro.is_observable("venus", 20, -4, -4.2, 0.5, 10)
    assert not astro.is_observable("uranus", 20, -4, 5.7, 0.5, 10)
    assert astro.is_observable("uranus", 20, -16, 5.7, 0.5, 10)
    # Below the minimum altitude nothing counts.
    assert not astro.is_observable("jupiter", 5, -30, -2.5, 0.5, 10)
    # The Moon in daylight, unless it is new.
    assert astro.is_observable("moon", 30, 40, -10, 0.5, 10)
    assert not astro.is_observable("moon", 30, 40, -10, 0.001, 10)


def test_time_round_trip() -> None:
    when = utc(2025, 3, 14, 6, 58, 30)
    assert abs((astro.from_time(astro.to_time(when)) - when).total_seconds()) < 0.01


def test_compute_now() -> None:
    sky = astro.compute_now(LONDON, utc(2025, 12, 14, 22, 0))
    assert sky.darkness == "night"
    assert set(sky.bodies) == {"moon", *astro.PLANETS}
    jupiter = sky.bodies["jupiter"]
    assert jupiter.constellation == "Gemini"
    assert jupiter.altitude > 20
    assert jupiter.observable
    assert jupiter.next_rise is not None
    assert sky.moon.phase in astro.MOON_PHASES
    assert sky.moon.next_full_moon > sky.computed_at


def test_tonight_winter_london() -> None:
    now = utc(2025, 12, 14, 12, 0)
    tonight = astro.compute_tonight(LONDON, now)
    assert tonight.night is not None
    assert tonight.night.start > now
    assert 15 < tonight.night.hours < 17
    assert tonight.astronomical_dusk is not None
    assert tonight.astronomical_dawn is not None
    assert tonight.night.start < tonight.astronomical_dusk < tonight.astronomical_dawn
    assert 11 < tonight.dark_hours < 13
    assert 0 < tonight.dark_sky_hours <= tonight.dark_hours
    for window in tonight.dark_sky_windows:
        assert tonight.night.start <= window.start < window.end <= tonight.night.end
    assert "jupiter" in tonight.bodies
    jupiter = tonight.bodies["jupiter"]
    assert jupiter.visible_from <= jupiter.best_time <= jupiter.visible_until


def test_tonight_during_the_night() -> None:
    now = utc(2025, 12, 15, 2, 0)
    tonight = astro.compute_tonight(LONDON, now)
    assert tonight.night is not None
    assert tonight.night.contains(now)


def test_tonight_polar_day() -> None:
    tonight = astro.compute_tonight(TROMSO, utc(2025, 6, 21, 12, 0))
    assert tonight.night is None
    assert tonight.bodies == {}
    assert tonight.dark_hours == 0


def test_tonight_polar_night() -> None:
    tonight = astro.compute_tonight(TROMSO, utc(2025, 12, 21, 12, 0))
    assert tonight.night is not None
    assert tonight.night.hours >= 23


def test_summer_has_no_astronomical_darkness_in_london() -> None:
    tonight = astro.compute_tonight(LONDON, utc(2025, 6, 21, 12, 0))
    assert tonight.night is not None
    assert tonight.astronomical_dusk is None
    assert tonight.dark_hours == 0


def test_total_lunar_eclipse_march_2025() -> None:
    event = astro.next_lunar_eclipse(NEW_YORK, utc(2025, 3, 1))
    assert event is not None
    assert event.details["eclipse_kind"] == "total"
    assert abs(event.time - utc(2025, 3, 14, 6, 58, 43)) < timedelta(minutes=5)
    assert "total_begin" in event.details


def test_lunar_eclipse_in_progress_is_found() -> None:
    event = astro.next_lunar_eclipse(NEW_YORK, utc(2025, 3, 14, 7, 30))
    assert event is not None
    assert event.details["in_progress"]


def test_total_solar_eclipse_april_2024() -> None:
    event = astro.next_solar_eclipse(DALLAS, utc(2024, 4, 1))
    assert event is not None
    assert event.details["eclipse_kind"] == "total"
    assert abs(event.time - utc(2024, 4, 8, 18, 42)) < timedelta(minutes=5)
    assert event.details["obscuration"] == 100


def test_meteor_showers_wrap_the_year() -> None:
    showers = astro.meteor_showers(
        LONDON, utc(2026, 1, 1, 12), ZoneInfo("Europe/London")
    )
    quadrantids = next(s for s in showers if s.name == "Quadrantids")
    assert quadrantids.active
    assert quadrantids.peak_night.isoformat() == "2026-01-02"
    assert quadrantids.best_time is not None


def test_geminids_best_time() -> None:
    showers = astro.meteor_showers(
        LONDON, utc(2025, 12, 1, 12), ZoneInfo("Europe/London")
    )
    geminids = next(s for s in showers if s.name == "Geminids")
    assert not geminids.active
    assert geminids.best_time is not None
    # The radiant culminates around 02:00 local time, high in the sky.
    assert utc(2025, 12, 14, 0) < geminids.best_time < utc(2025, 12, 14, 4)
    assert geminids.radiant_altitude > 60


def test_southern_shower_radiant_never_rises_far_north() -> None:
    # The radiant at -16 degrees stays below the horizon from Tromso.
    showers = astro.meteor_showers(
        TROMSO, utc(2025, 7, 20, 12), ZoneInfo("Europe/Oslo")
    )
    delta = next(s for s in showers if s.name == "Southern Delta Aquariids")
    assert delta.best_time is None
    assert delta.radiant_altitude < 0


def test_celestial_events() -> None:
    now = utc(2025, 1, 1)
    events = astro.celestial_events(now)
    assert events == sorted(events, key=lambda e: e.time)
    assert all(e.time > now for e in events)
    mars = next(
        e for e in events if e.kind == "opposition" and e.details["body"] == "mars"
    )
    assert mars.time.date().isoformat() == "2025-01-16"
    kinds = {e.kind for e in events}
    assert {"equinox", "solstice", "opposition", "greatest_elongation"} <= kinds


def test_events_expire_only_on_future_times() -> None:
    now = utc(2025, 8, 14, 12)
    events = astro.compute_events(LONDON, now, ZoneInfo("Europe/London"))
    assert events.expires is not None
    assert events.expires > now
    assert any(s.name == "Perseids" and s.active for s in events.active_showers)
