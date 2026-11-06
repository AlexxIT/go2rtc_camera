import probatio
import yarl
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.helpers.selector import (
    BooleanSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import DOMAIN

CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required("url"): TextSelector(),
        probatio.Optional("two_way"): BooleanSelector(),
        probatio.Optional("server"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
    },
)


class XConfigFlow(ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input:
            raw = user_input["url"]
            url = yarl.URL(raw)
            title = f"{url.scheme} {url.host}" if url.scheme and url.host else raw
            return self.async_create_entry(title=title, data={}, options=user_input)

        return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> XOptionsFlow:
        return XOptionsFlow()


class XOptionsFlow(OptionsFlowWithReload):
    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA, self.config_entry.options
            ),
        )
