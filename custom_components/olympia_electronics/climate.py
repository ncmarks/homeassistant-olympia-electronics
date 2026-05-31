"""Support for the Olympia Electronics Thermostat."""
import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (HVACMode, ClimateEntityFeature, HVACAction)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_PRECISION,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_PRECISION,
    DOMAIN,
)
from .coordinator import OlympiaElectronicsCoordinator
from .entity import OlympiaBaseEntity


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Olympia Electronics climate platform from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        OlympiaClimateEntity(
            coordinator=coordinator,
            device_id=device_id,
            name=device_data.get("device", {}).get("name", f"Thermostat {device_id}"),
        )
        for device_id, device_data in (coordinator.data or {}).items()
    ]

    async_add_entities(entities)


class OlympiaClimateEntity(OlympiaBaseEntity, ClimateEntity):
    """Representation of an Olympia Electronics Thermostat."""

    _attr_should_poll = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]

    def __init__(
        self,
        coordinator: OlympiaElectronicsCoordinator,
        device_id: str,
        name: str,
    ):
        """Initialize thermostat."""
        super().__init__(coordinator, device_id, name)
        self._attr_unique_id = f"{device_id}_climate"
        options = coordinator.config_entry.options
        self._attr_min_temp = options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)
        self._attr_max_temp = options.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)
        self._precision = options.get(CONF_PRECISION, DEFAULT_PRECISION)

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """Convert to float, or None when the value is missing or invalid."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._to_float(self._status.get("temperature"))

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._to_float(
            self._setting.get("setpoint", self._status.get("setpoint"))
        )

    @property
    def hvac_mode(self):
        """Return the selected operation mode (HEAT when on, OFF when off).

        This reflects the *configured* mode, not the current activity.
        Whether the burner is actively firing is reported via hvac_action.
        """
        return HVACMode.HEAT if self._status.get("is_on") else HVACMode.OFF

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        if not self._status.get("is_on"):
            return HVACAction.OFF
        if self._status.get("burner_on"):
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def precision(self):
        """Return the precision."""
        return self._precision

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature.

        Follows the configured precision (0.1 / 0.5 / 1) instead of a fixed
        value so the UI step and the displayed precision stay consistent.
        """
        return self._precision

    @property
    def extra_state_attributes(self):
        """Return extra device attributes."""
        return {
            "boiler_on": self._status.get("boiler_on", False),
            "burner_on": self._status.get("burner_on", False),
            "is_online": self._status.get("is_online", False),
            "rssi": self._status.get("rssi"),
        }

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        _LOGGER.debug("async_set_hvac_mode called: %s", hvac_mode)
        if hvac_mode not in (HVACMode.HEAT, HVACMode.OFF):
            _LOGGER.debug("Unsupported HVAC mode %s, ignoring", hvac_mode)
            return
        await self.coordinator.async_send_update(
            self._device_id,
            turn_on=(hvac_mode == HVACMode.HEAT),
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature (clamped)."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        try:
            new_temp = float(temperature)
        except (TypeError, ValueError):
            _LOGGER.warning("Invalid temperature value provided: %s", temperature)
            return

        new_temp = min(max(new_temp, self._attr_min_temp), self._attr_max_temp)
        await self.coordinator.async_send_update(
            self._device_id,
            setpoint=new_temp,
        )
