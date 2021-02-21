"""AppDaemon app to use ISY994 Insteon KeypadLinc Secondary and RemoteLinc buttons to control non-ISY994 devices."""

from typing import Any, List, Optional, Type, TypeVar, Union

import hassapi as hass
import voluptuous as vol

DIMMING_SPEED = 1
DIMMING_TIMEOUT = 10

ISY_CONTROL_EVENT = "isy994_control"
ISY_ON = "DON"
ISY_FAST_ON = "DFON"
ISY_OFF = "DOF"
ISY_FAST_OFF = "DFOF"
ISY_FADE_UP = "FDUP"
ISY_FADE_DOWN = "FDDOWN"
ISY_FADE_STOP = "FDSTOP"

CONF_RESPONDERS = "responders"
CONF_ENTITY_ID = "entity_id"
CONF_CLASS = "class"
CONF_CONTROL = "control"
CONF_MODULE = "module"
CONF_CONTROLLERS = "controllers"
CONF_FOLLOWER_ENTITY = "follower_entity"
CONF_TURN_ON_DATA = "turn_on_data"
CONF_FAST_ON_DATA = "fast_on_data"
CONF_TURN_OFF_DATA = "turn_off_data"
CONF_FAST_OFF_DATA = "fast_off_data"
CONF_DIMMING_STEP = "dimming_step"
CONF_DIMMING_SPEED = "dimming_speed"
CONF_DIMMING_DATA = "dimming_data"

DOMAIN_LIGHT = "light"
SERVICE_ON = "turn_on"
SERVICE_OFF = "turn_off"

ACTIVE = "active"
FADE_TIMER = "fade_timer"

MAP_SERVICES = {
    ISY_ON: SERVICE_ON,
    ISY_FAST_ON: SERVICE_ON,
    ISY_OFF: SERVICE_OFF,
    ISY_FAST_OFF: SERVICE_OFF,
}

MAP_SERVICE_DATA = {
    ISY_ON: CONF_TURN_ON_DATA,
    ISY_FAST_ON: CONF_FAST_ON_DATA,
    ISY_OFF: CONF_TURN_OFF_DATA,
    ISY_FAST_OFF: CONF_FAST_OFF_DATA,
}

APP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODULE): str,
        vol.Required(CONF_CLASS): str,
        vol.Required(CONF_RESPONDERS): vol.All(
            [
                vol.Schema(
                    {
                        vol.Required(CONF_ENTITY_ID): entity_id,
                        vol.Optional(CONF_TURN_ON_DATA, default={}): dict,
                        vol.Optional(CONF_FAST_ON_DATA, default={}): dict,
                        vol.Optional(CONF_TURN_OFF_DATA, default={}): dict,
                        vol.Optional(CONF_FAST_OFF_DATA, default={}): dict,
                        vol.Optional(CONF_DIMMING_STEP, default=50): vol.All(
                            int, vol.Range(min=1, max=255)
                        ),
                        vol.Optional(CONF_DIMMING_DATA, default={}): dict,
                    }
                )
            ],
            vol.Length(min=1),
        ),
        vol.Required(CONF_CONTROLLERS): entity_ids,
        vol.Optional(CONF_FOLLOWER_ENTITY): entity_id,
        # Dimming speed is defaulted to 1 second (lowest resolution for AppDaemon)
        # vol.Optional(CONF_DIMMING_SPEED, default=1): vol.All(
        #     int, vol.Range(min=1, max=5)
        # ),
    },
    extra=vol.ALLOW_EXTRA,
)

# Schema Validation Functions
T = TypeVar("T")  # pylint: disable=invalid-name


def entity_id(value: Any) -> str:
    """Validate if a given object is an entity ID."""
    value = str(value).lower()
    if "." in value:
        return value

    raise vol.Invalid("Invalid entity ID: {0}".format(value))


def entity_ids(value: Union[str, List]) -> List[str]:
    """Validate Entity IDs."""
    if value is None:
        raise vol.Invalid("Entity IDs can not be None")
    if isinstance(value, str):
        value = [ent_id.strip() for ent_id in value.split(",")]

    return [entity_id(ent_id) for ent_id in value]


class ISY994Buttons(hass.Hass):
    """Class for ISY994 Insteon Button Controls."""

    def initialize(self):
        """Initialize a new ISY994 Insteon Buttons class."""
        # Validate app configuration
        try:
            self.validated_args = APP_SCHEMA(self.args)
        except vol.Invalid as err:
            self.log(f"Invalid configuration: {err}", level="ERROR", log="error_log")
            return

        # Process App Arguments
        self.responders = self.validated_args.get(CONF_RESPONDERS)
        self.controllers = self.validated_args.get(CONF_CONTROLLERS)
        self.follower_entity = self.validated_args.get(CONF_FOLLOWER_ENTITY)
        # self.dimming_speed = self.validated_args.get(CONF_DIMMING_SPEED)

        # Setup Listeners
        self.fade_handler = None
        self.fade_watchdog_handler = None
        self.event_listeners = []
        self.state_listeners = []

        for entity in self.responders:
            self.state_listeners.append(
                self.listen_state(
                    self.entity_state_change_callback, entity[CONF_ENTITY_ID]
                )
            )
            entity[ACTIVE] = False

        for controller in self.controllers:
            self.event_listeners.append(
                self.listen_event(
                    self.isy994_control_event_callback,
                    ISY_CONTROL_EVENT,
                    entity_id=controller,
                )
            )

    def isy994_control_event_callback(self, event_name, data, kwargs):
        """Handle an ISY994 Control Event."""
        control = data.get(CONF_CONTROL)
        controller = data.get(CONF_ENTITY_ID)
        self.log(f"Event received for {controller}, control: {control}", level="DEBUG")

        if control in MAP_SERVICES:
            for entity in self.responders:
                domain = entity[CONF_ENTITY_ID].split(".")[0]
                entity[ACTIVE] = True
                self.call_service(
                    f"{domain}/{MAP_SERVICES.get(control)}",
                    entity_id=entity[CONF_ENTITY_ID],
                    **entity.get(MAP_SERVICE_DATA.get(control), {}),
                )
            return
        if control in [ISY_FADE_DOWN, ISY_FADE_STOP, ISY_FADE_UP]:
            self.fade_control(control)
            return

        self.log(
            f"No action assigned for {control} command on {controller}", level="INFO"
        )

    def entity_state_change_callback(self, entity_id, attribute, old, new, kwargs):
        """Handle a state change for a watched entity."""
        entity_changed = next(e for e in self.responders if e[CONF_ENTITY_ID] == entity_id)
        if entity_changed[ACTIVE]:
            # Controller was the one that changed the state, clear flag and ignore.
            entity_changed[ACTIVE] = False
            return

        self.log(
            f"{entity_id} changed to {new}, but not due to controller.", level="DEBUG"
        )

        # Update the ISY Scene/Devices to match the device status.
        if self.follower_entity and new in ["on", "off"]:
            domain = self.follower_entity.split(".")[0]
            extra_data = {}
            if domain == DOMAIN_LIGHT:
                brightness = self.get_state(entity_id=entity_id, attribute="brightness", default=None)
                if brightness:
                    extra_data["brightness"] = brightness
            self.call_service(f"{domain}/turn_{new}", entity_id=self.follower_entity, **extra_data)

    def fade_control(self, control):
        """Handle a Fade control event from a controller."""
        if self.fade_handler is not None:
            self.cancel_timer(self.fade_handler)
            self.fade_handler = None
        if self.fade_watchdog_handler is not None:
            self.cancel_timer(self.fade_watchdog_handler)
            self.fade_watchdog_handler = None

        if control in [ISY_FADE_UP, ISY_FADE_DOWN]:
            fade_direction = -1 if control == ISY_FADE_DOWN else 1
            self.fade_handler = self.run_every(
                self.fade_callback, "now", DIMMING_SPEED, direction=fade_direction
            )
            self.fade_watchdog_handler = self.run_in(
                self.fade_watchdog, DIMMING_TIMEOUT
            )

    def fade_callback(self, kwargs):
        """Handle the timed fade service calls."""
        for entity in self.responders:
            domain = entity[CONF_ENTITY_ID].split(".")[0]
            entity[ACTIVE] = True
            if domain != DOMAIN_LIGHT:
                continue
            self.call_service(
                f"{domain}/{SERVICE_ON}",
                entity_id=entity[CONF_ENTITY_ID],
                brightness_step=(entity[CONF_DIMMING_STEP] * kwargs["direction"]),
                **entity[CONF_DIMMING_DATA],
            )

    def fade_watchdog(self, kwargs):
        """Watch for a missed FDSTOP event and prevent infinite loop."""
        if self.fade_handler is not None:
            self.cancel_timer(self.fade_handler)
            self.fade_handler = None
        self.fade_watchdog_handler = None
