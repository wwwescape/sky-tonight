"""Base entity for Sky Tonight."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SkyTonightCoordinator

BODY_NAMES = {
    "moon": "Moon",
    "mercury": "Mercury",
    "venus": "Venus",
    "mars": "Mars",
    "jupiter": "Jupiter",
    "saturn": "Saturn",
    "uranus": "Uranus",
    "neptune": "Neptune",
}

# Lists that can grow large; kept in the state but not in the recorder.
UNRECORDED_ATTRIBUTES = frozenset(
    {"planets", "windows", "upcoming", "active_showers", "upcoming_showers"}
)


class SkyTonightEntity(CoordinatorEntity[SkyTonightCoordinator]):
    """An entity backed by the Sky Tonight coordinator."""

    _attr_has_entity_name = True
    _unrecorded_attributes = UNRECORDED_ATTRIBUTES

    def __init__(
        self,
        coordinator: SkyTonightCoordinator,
        description: EntityDescription,
        body: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.body = body
        entry = coordinator.config_entry
        self._attr_unique_id = (
            f"{entry.entry_id}_{body}_{description.key}"
            if body
            else f"{entry.entry_id}_{description.key}"
        )
        if body:
            self._attr_translation_placeholders = {"body": BODY_NAMES[body]}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Sky Tonight",
            model="Astronomy Engine",
            entry_type=DeviceEntryType.SERVICE,
        )
