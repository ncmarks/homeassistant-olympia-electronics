"""Olympia Electronics integration."""
import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

_LOGGER: logging.Logger = logging.getLogger(__name__)

DOMAIN: Final = "olympia_electronics"

CONF_MIN_TEMP = "min_temp"
CONF_MAX_TEMP = "max_temp"
CONF_PRECISION = "precision"

DEFAULT_MIN_TEMP = 10.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_PRECISION = 0.1

PLATFORMS = [Platform.CLIMATE, Platform.BINARY_SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Olympia Electronics from a config entry."""
    from .coordinator import OlympiaElectronicsCoordinator

    coordinator = OlympiaElectronicsCoordinator(
        hass,
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        config_entry=entry,
    )

    try:
        await coordinator.async_validate_credentials()
    except UpdateFailed as err:
        msg = str(err)
        if "Login" in msg or "401" in msg:
            raise ConfigEntryAuthFailed(err) from err
        raise ConfigEntryNotReady(err) from err

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


@callback
def _migrate_unique_id(entity_entry: er.RegistryEntry) -> dict | None:
    """Migrate legacy entity unique_ids to the unified {device_id}_{key} scheme."""
    unique_id = entity_entry.unique_id

    if entity_entry.domain == "climate" and unique_id.startswith("olympia_electronics_"):
        device_id = unique_id[len("olympia_electronics_"):]
        return {"new_unique_id": f"{device_id}_climate"}

    if entity_entry.domain == "switch" and unique_id.endswith("_boiler_switch"):
        device_id = unique_id[: -len("_boiler_switch")]
        return {"new_unique_id": f"{device_id}_boiler"}

    return None


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change so entities pick up new values."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
