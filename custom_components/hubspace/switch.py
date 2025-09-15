"""Home Assistant entity for interacting with Afero Switch."""

from functools import partial
from typing import Any

from aioafero.v1 import AferoBridgeV1, LightController
from aioafero.v1.controllers.event import EventType
from aioafero.v1.controllers.switch import SwitchController
from aioafero.v1.models.switch import Switch
from aioafero.v1.models import Light
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import HubspaceBridge
from .const import DOMAIN
from .entity import HubspaceBaseEntity, update_decorator


class HubspaceNightLightSwitch(HubspaceBaseEntity, SwitchEntity):
    """Representation of a night-light switch for Afero lights that support it."""

    def __init__(
        self,
        bridge: HubspaceBridge,
        controller: LightController,
        resource: Light,
    ) -> None:
        """Initialize an Afero night-light switch."""
        super().__init__(bridge, controller, resource)
        self._attr_name = f"{self.resource.friendly_name} Night Light"
        self._attr_unique_id = f"{self.resource.id}_night_light"

    @property
    def is_on(self) -> bool | None:
        """Determine if the night-light is currently on."""
        try:
            if not hasattr(self.resource, 'color_mode') or not self.resource.color_mode:
                return False
            return self.resource.color_mode.mode == "night-light"
        except (AttributeError, TypeError):
            return False

    @update_decorator
    async def async_turn_on(
        self,
        **kwargs: Any,
    ) -> None:
        """Turn on the night-light."""
        self.logger.debug("Turning on night-light for entity %s", self.resource.id)
        await self.bridge.async_request_call(
            self.controller.set_state,
            device_id=self.resource.id,
            on=True,
            color_mode="night-light",
        )

    @update_decorator
    async def async_turn_off(
        self,
        **kwargs: Any,
    ) -> None:
        """Turn off the night-light (revert to white mode)."""
        self.logger.debug("Turning off night-light for entity %s", self.resource.id)
        await self.bridge.async_request_call(
            self.controller.set_state,
            device_id=self.resource.id,
            on=True,
            color_mode="white",
        )


class HubspaceSwitch(HubspaceBaseEntity, SwitchEntity):
    """Representation of an Afero switch."""

    def __init__(
        self,
        bridge: HubspaceBridge,
        controller: SwitchController,
        resource: Switch,
        instance: str | None,
    ) -> None:
        """Initialize an Afero switch."""
        super().__init__(bridge, controller, resource, instance=instance)
        self.instance = instance

    @property
    def is_on(self) -> bool | None:
        """Determines if the switch is on."""
        feature = self.resource.on.get(self.instance, None)
        if feature:
            return feature.on
        return None

    @update_decorator
    async def async_turn_on(
        self,
        **kwargs: Any,
    ) -> None:
        """Turn on the entity."""
        self.logger.debug("Adjusting entity %s with %s", self.resource.id, kwargs)
        await self.bridge.async_request_call(
            self.controller.set_state,
            device_id=self.resource.id,
            on=True,
            instance=self.instance,
        )

    @update_decorator
    async def async_turn_off(
        self,
        **kwargs: Any,
    ) -> None:
        """Turn off the entity."""
        self.logger.debug("Adjusting entity %s with %s", self.resource.id, kwargs)
        await self.bridge.async_request_call(
            self.controller.set_state,
            device_id=self.resource.id,
            on=False,
            instance=self.instance,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities."""
    bridge: HubspaceBridge = hass.data[DOMAIN][config_entry.entry_id]
    api: AferoBridgeV1 = bridge.api
    controller: SwitchController = api.switches
    light_controller: LightController = api.lights
    make_entity = partial(HubspaceSwitch, bridge, controller)
    make_night_light_entity = partial(HubspaceNightLightSwitch, bridge, light_controller)

    def has_night_light_capability(light_resource: Light) -> bool:
        """Check if a light supports night-light functionality."""
        try:
            # Check if the light has a color-mode function with night-light option
            for func in light_resource.functions:
                if func.get("functionClass") == "color-mode":
                    for value in func.get("values", []):
                        if value.get("name") == "night-light":
                            return True
        except (AttributeError, TypeError):
            pass
        return False

    def get_unique_entities(hs_resource: Switch) -> list[HubspaceSwitch]:
        instances = hs_resource.on.keys()
        return [
            make_entity(hs_resource, instance)
            for instance in instances
            if len(instances) == 1 or instance is not None
        ]

    def get_night_light_entities(light_resource: Light) -> list[HubspaceNightLightSwitch]:
        """Get night-light switch entities for lights that support it."""
        if has_night_light_capability(light_resource):
            return [make_night_light_entity(light_resource)]
        return []

    @callback
    def async_add_entity(event_type: EventType, hs_resource: Switch) -> None:
        """Add an entity."""
        async_add_entities(get_unique_entities(hs_resource))

    @callback
    def async_add_light_entity(event_type: EventType, light_resource: Light) -> None:
        """Add a night-light switch entity for lights that support it."""
        async_add_entities(get_night_light_entities(light_resource))

    # add all current switch items in controller
    entities: list[HubspaceSwitch] = []
    for resource in controller:
        entities.extend(get_unique_entities(resource))
    
    # add all current night-light switch entities from lights
    night_light_entities: list[HubspaceNightLightSwitch] = []
    for light_resource in light_controller:
        night_light_entities.extend(get_night_light_entities(light_resource))
    
    # Combine all entities for addition
    all_entities = entities + night_light_entities
    async_add_entities(all_entities)
    
    # register listener for new switch entities
    config_entry.async_on_unload(
        controller.subscribe(async_add_entity, event_filter=EventType.RESOURCE_ADDED)
    )
    
    # register listener for new light entities (for night-light switches)
    config_entry.async_on_unload(
        light_controller.subscribe(async_add_light_entity, event_filter=EventType.RESOURCE_ADDED)
    )
