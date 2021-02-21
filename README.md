# ISY994 Insteon Buttons

AppDaemon app to use ISY994 Insteon KeypadLinc Secondary and RemoteLinc buttons to control non-ISY994 devices.

This AppDaemon app allows you to use button presses from Insteon KeypadLinc and RemoteLinc controllers paired to
and ISY994 to control non-ISY994 devices. For example, you can use a KeypadLinc Secondary button to dim a
Zigbee Lamp paired through Home Assistant. It also supports using something like a Insteon Dimmer Switch to
control a non-Insteon device that is not paired with the ISY.

The following Insteon Commands are supported: On (`DON`), Off (`DOF`), Fast On (`DFON`), Fast Off (`DFOF`),
Fade Up (`FDUP`), Fade Down (`FDDOWN`), Fade Stop (`FDSTOP`). For dimmable lights, you can also supply parameters
to use for each command.

It also supports syncing status back to the ISY buttons (for non-battery devices only), so if the end device is
controlled by something else (e.g. Lovelace or Alexa), it will update the keypad/switch to match.

## Pre-Requisites

Insteon KeypadLinc Secondary buttons cannot be controlled directly. If you want this app to keep the button
status in-sync with the end device state, you must first create a Scene in the ISY
containing just the button(s) as a `controller`. If this is set to a dimmable device (e.g. a DimmerLinc), the exact
brightness level will also be synced back.

## Options

Key | Required | Description | Type/Range
------------ | ------------- | ------------- | -------------
module | True | AppDaemon Module description. | `"isy994-buttons"`
class | True | AppDaemon Class name. | `"ISY994Buttons"`
responders | True | The devices to control and service data to use. See Responders below. | List Responders `dict` objects, see below.
controllers | True | The controllers to listen to for `isy994_control` events (e.g. the entity for the button). | List of Entity IDs
follower_entity | False | An Entity ID representing an ISY Scene or device to keep in sync with the end device, see Pre-Requisites.

### Responders

The Responders to control with this app.

Key | Required | Description | Type/Range
------------ | ------------- | ------------- | -------------
entity_id | True | The Entity ID of the device to control. | Entity ID
turn_on_data | False | [Service Data](https://www.home-assistant.io/integrations/light/#service-lightturn_on) to use for a regular Turn On event. | `dict`
fast_on_data | False | [Service Data](https://www.home-assistant.io/integrations/light/#service-lightturn_on) to use for a Fast On event. | `dict`
turn_off_data | False | [Service Data](https://www.home-assistant.io/integrations/light/#service-lightturn_off) to use for a regular Turn Off event. | `dict`
fast_off_data | False | [Service Data](https://www.home-assistant.io/integrations/light/#service-lightturn_off) to use for a Fast Off event. | `dict`
dimming_step | False | Step size for each dimming step, called once per second while a button is held down. Note: if using a KeypadLinc button you hold down the button for more than ~8 sec before entering a pairing mode, keep this in mind when setting the step size. | `int`, 1-255; default: 50
dimming_data | False | [Service Data](https://www.home-assistant.io/integrations/light/#service-lightturn_on) to use while dimming (e.g. to set the color). | `dict`

## Example apps.yaml

```yaml
isy_control_test:
  module: isy994-buttons
  class: ISY994Buttons
  controllers:
    - sensor.driveway_kp_e
  responders:
    - entity_id: light.living_room_lamp
      turn_on_data:
        transition: 1
        brightness: 128
      fast_on_data:
        transition: 0
        brightness: 255
      fast_off_data:
        transition: 0
  # The follower entity is an ISY Scene that only contains the button.
  follower_entity: switch.p_driveway_kp_e
  log_level: DEBUG
```
