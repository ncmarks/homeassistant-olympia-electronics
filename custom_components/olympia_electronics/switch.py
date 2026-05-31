"""Switch platform for Olympia Electronics boiler control."""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .entity import OlympiaBaseEntity, device_has_field

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Olympia Electronics switches from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        OlympiaBoilerSwitch(
            coordinator,
            device_id,
            device_data.get("device", {}).get("name", f"Thermostat {device_id}"),
        )
        for device_id, device_data in (coordinator.data or {}).items()
        if device_has_field(device_data, "boiler_on")
    ]

    if entities:
        async_add_entities(entities)
        _LOGGER.debug("Added %d boiler switches", len(entities))


class OlympiaBoilerSwitch(OlympiaBaseEntity, SwitchEntity):
    """Representation of an Olympia Electronics boiler switch."""

    _attr_icon = "mdi:fire"

    def __init__(self, coordinator, device_id: str, device_name: str):
        """Initialize the switch."""
        super().__init__(coordinator, device_id, device_name)
        self._attr_name = "Boiler"
        self._attr_unique_id = f"{device_id}_boiler"

    @property
    def is_on(self) -> bool:
        """Return the live boiler state."""
        return bool(self._status.get("boiler_on", False))

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the boiler on."""
        _LOGGER.debug("async_turn_on called for %s", self._device_id)
        await self.coordinator.async_send_update(self._device_id, boiler_on=True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the boiler off."""
        _LOGGER.debug("async_turn_off called for %s", self._device_id)
        await self.coordinator.async_send_update(self._device_id, boiler_on=False)
