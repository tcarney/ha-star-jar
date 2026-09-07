"""Config flow for Star Jar: one entry per child, options editable afterwards."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CONF_AI_TASK_ENTITY,
    CONF_CHILD_NAME,
    CONF_INSTRUCTIONS,
    CONF_JAR_SIZE,
    DEFAULT_INSTRUCTIONS,
    DEFAULT_JAR_SIZE,
    DOMAIN,
)

_USER_SCHEMA = vol.Schema({vol.Required(CONF_CHILD_NAME): TextSelector()})

_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_JAR_SIZE, default=DEFAULT_JAR_SIZE): NumberSelector(
            NumberSelectorConfig(min=1, max=100, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_AI_TASK_ENTITY): EntitySelector(EntitySelectorConfig(domain="ai_task")),
        vol.Optional(CONF_INSTRUCTIONS, default=DEFAULT_INSTRUCTIONS): TextSelector(TextSelectorConfig(multiline=True)),
    }
)


class StarJarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the child's name; everything else is an option with a default."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> StarJarOptionsFlow:
        """Return the options flow."""
        return StarJarOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create a jar named after the child."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_CHILD_NAME].strip()
            if not name:
                errors[CONF_CHILD_NAME] = "invalid_name"
            else:
                await self.async_set_unique_id(name.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={CONF_CHILD_NAME: name},
                    options={CONF_JAR_SIZE: DEFAULT_JAR_SIZE, CONF_INSTRUCTIONS: DEFAULT_INSTRUCTIONS},
                )

        return self.async_show_form(step_id="user", data_schema=_USER_SCHEMA, errors=errors)


class StarJarOptionsFlow(OptionsFlowWithReload):
    """Jar size, narration entity and persona text. Saving reloads the entry."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show and save the options."""
        if user_input is not None:
            # The number selector hands back a float; the jar counts whole stars.
            user_input[CONF_JAR_SIZE] = int(user_input[CONF_JAR_SIZE])
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(_OPTIONS_SCHEMA, self.config_entry.options),
        )
