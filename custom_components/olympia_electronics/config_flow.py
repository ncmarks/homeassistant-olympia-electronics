"""Config flow for Olympia Electronics."""
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from . import (
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_PRECISION,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_PRECISION,
    DOMAIN,
)
from .coordinator import CannotConnect, InvalidAuth, async_login

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class OlympiaElectronicsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Olympia Electronics."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return OlympiaElectronicsOptionsFlow()

    async def _validate(self, user_input) -> dict:
        """Validate credentials with a standalone login; return an errors dict."""
        session = async_get_clientsession(self.hass)
        try:
            await async_login(
                session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
        except InvalidAuth:
            return {"base": "invalid_auth"}
        except CannotConnect:
            return {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error validating Olympia Electronics credentials")
            return {"base": "unknown"}
        return {}

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()
            errors = await self._validate(user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        """Handle reauthentication after credentials expire."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle reauth confirmation."""
        errors = {}

        if user_input is not None:
            errors = await self._validate(user_input)
            if not errors:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_mismatch(reason="account_mismatch")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


def _temp_selector() -> NumberSelector:
    """Build the °C number selector used for the min/max temperature fields."""
    return NumberSelector(
        NumberSelectorConfig(
            min=0,
            max=40,
            step=0.5,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="°C",
        )
    )


class OlympiaElectronicsOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle the options flow for Olympia Electronics.

    Lets the user tune the temperature range and step used by the climate
    entities. ``OptionsFlowWithReload`` reloads the entry automatically when
    the options change, so entities pick up the new values.
    """

    async def async_step_init(self, user_input=None):
        """Manage the temperature range and precision options."""
        errors = {}

        if user_input is not None:
            if user_input[CONF_MIN_TEMP] >= user_input[CONF_MAX_TEMP]:
                errors["base"] = "min_max"
            else:
                return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MIN_TEMP,
                    default=options.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP),
                ): _temp_selector(),
                vol.Required(
                    CONF_MAX_TEMP,
                    default=options.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP),
                ): _temp_selector(),
                vol.Required(
                    CONF_PRECISION,
                    default=options.get(CONF_PRECISION, DEFAULT_PRECISION),
                ): vol.In([0.1, 0.5, 1.0]),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
