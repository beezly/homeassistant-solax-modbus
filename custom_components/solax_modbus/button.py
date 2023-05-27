from .const import ATTR_MANUFACTURER, DOMAIN, CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR
from .const import WRITE_DATA_LOCAL, WRITE_MULTISINGLE_MODBUS, WRITE_SINGLE_MODBUS, WRITE_MULTI_MODBUS
from .const import autorepeat_set
from homeassistant.components.button import PLATFORM_SCHEMA, ButtonEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from typing import Any, Dict, Optional
from time import time
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities) -> None:
    if entry.data: # old style - remove soon
        hub_name = entry.data[CONF_NAME]
        modbus_addr = entry.data.get(CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR)
    else: # new style
        hub_name = entry.options[CONF_NAME]
        modbus_addr = entry.options.get(CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR)
    hub = hass.data[DOMAIN][hub_name]["hub"]

    device_info = {
        "identifiers": {(DOMAIN, hub_name)},
        "name": hub_name,
        "manufacturer": ATTR_MANUFACTURER,
    }
    plugin = hub.plugin
    entities = []
    for button_info in plugin.BUTTON_TYPES:
        if plugin.matchInverterWithMask(hub._invertertype, button_info.allowedtypes, hub.seriesnumber, button_info.blacklist):
            button = SolaXModbusButton( hub_name, hub, modbus_addr, device_info, button_info )
            entities.append(button)
            if button_info.key == plugin.wakeupButton(): hub.wakeupButton = button_info
            if button_info.value_function: hub.computedButtons[button_info.key] = button_info
            elif button_info.command == None: _LOGGER.warning(f"button without command and without value_function found: {button_info.key}")
    async_add_entities(entities)
    _LOGGER.info(f"hub.wakeuButton: {hub.wakeupButton}")
    return True

class SolaXModbusButton(ButtonEntity):
    """Representation of an SolaX Modbus button."""

    def __init__(self,
                 platform_name,
                 hub,
                 modbus_addr,
                 device_info,
                 button_info
    ) -> None:
        """Initialize the button."""
        self._platform_name = platform_name
        self._hub = hub
        self._modbus_addr = modbus_addr
        self._attr_device_info = device_info
        self._name = button_info.name
        self._key = button_info.key
        self.button_info = button_info
        self._register = button_info.register
        self._command = button_info.command
        self._attr_icon = button_info.icon
        self._write_method = button_info.write_method

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._platform_name} {self._name}"

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self._platform_name}_{self._key}"

    async def async_press(self) -> None:
        """Write the button value."""
        if self._write_method == WRITE_MULTISINGLE_MODBUS:
            LOGGER.info(f"writing {self._platform_name} button register {self._register} value {self._command}")
            self._hub.write_registers_single(unit=self._modbus_addr, address=self._register, payload=self._command)
        elif self._write_method == WRITE_SINGLE_MODBUS:
            _LOGGER.info(f"writing {self._platform_name} button register {self._register} value {self._command}")
            self._hub.write_register(unit=self._modbus_addr, address=self._register, payload=self._command)
        elif self._write_method == WRITE_MULTI_MODBUS:
            if self.button_info.autorepeat:
                duration = self._hub.data.get(self.button_info.autorepeat, 0)
                autorepeat_set(self._hub.data, self.button_info.key, time() + duration - 0.5 )
            if self.button_info.value_function:
                res = self.button_info.value_function(0, self.button_info, self._hub.data )
                if res: self._hub.write_registers_multi(unit=self._modbus_addr, address=self._register, payload=res)
