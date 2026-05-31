"""Olympia Electronics integration."""
import logging
from typing import Final

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .coordinator import OlympiaConfigEntry, OlympiaElectronicsCoordinator

_LOGGER: logging.Logger = logging.getLogger(__name__)

DOMAIN: Final = "olympia_electronics"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_PRECISION = "precision"

DEFAULT_MIN_TEMP = 10.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_PRECISION = 0.1

PLATFORMS = [Platform.CLIMATE, Platform.BINARY_SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: OlympiaConfigEntry) -> bool:
    """Set up Olympia Electronics from a config entry."""
    coordinator = OlympiaElectronicsCoordinator(
        hass,
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        config_entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OlympiaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
