"""Binary sensor platform for Olympia Electronics."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .entity import OlympiaBaseEntity, device_has_field


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Olympia Electronics binary sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        OlympiaBurnerSensor(
            coordinator,
            device_id,
            device_data.get("device", {}).get("name", f"Thermostat {device_id}"),
        )
        for device_id, device_data in (coordinator.data or {}).items()
        if device_has_field(device_data, "burner_on")
    ]

    if entities:
        async_add_entities(entities)


class OlympiaBurnerSensor(OlympiaBaseEntity, BinarySensorEntity):
    """Representation of Olympia Electronics burner (flame) state."""

    _attr_device_class = BinarySensorDeviceClass.HEAT

    def __init__(self, coordinator, device_id: str, device_name: str):
        """Initialize the sensor."""
        super().__init__(coordinator, device_id, device_name)
        self._attr_name = "Burner"
        self._attr_unique_id = f"{device_id}_burner"

    @property
    def is_on(self) -> bool:
        """Return the live burner state."""
        return bool(self._status.get("burner_on", False))
