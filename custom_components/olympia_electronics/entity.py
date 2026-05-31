"""Shared base entity for Olympia Electronics."""
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .coordinator import OlympiaElectronicsCoordinator


def device_has_field(device_data: dict, field: str) -> bool:
    """Return True if the device reports ``field`` in its status.

    The API exposes no explicit capability flags, so the presence of a
    status key is used to decide whether a feature exists. This keeps a
    model without a boiler from getting phantom boiler/burner entities.
    """
    return field in device_data.get("status", {})


class OlympiaBaseEntity(CoordinatorEntity):
    """Common base for entities tied to a single Olympia device.

    Provides the shared device registry info, availability logic and
    convenient accessors into the coordinator's per-device data so the
    platform modules don't each re-implement them.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OlympiaElectronicsCoordinator,
        device_id: str,
        device_name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name

    @property
    def _device_data(self) -> dict:
        """Return this device's full data block from the coordinator."""
        return (self.coordinator.data or {}).get(self._device_id, {})

    @property
    def _status(self) -> dict:
        """Return this device's live status dict."""
        return self._device_data.get("status", {})

    @property
    def _setting(self) -> dict:
        """Return this device's setting dict."""
        return self._device_data.get("setting", {})

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information, enriched with model and firmware."""
        device = self._device_data.get("device", {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Olympia Electronics",
            model=device.get("type_name") or "Smart Thermostat",
            name=self._device_name,
            sw_version=device.get("firmware_version"),
        )

    @property
    def available(self) -> bool:
        """Return True when the last poll succeeded and the device is online."""
        return self.coordinator.last_update_success and bool(
            self._status.get("is_online", False)
        )
