(https://img.shields.io/github/release/fondberg/easee_hass.svg?1)](https://github.com/fondberg/easee_hass) ![Maintenance](https://img.shields.io/maintenance/yes/2020.svg)

[![Buy me a coffee](https://img.shields.io/static/v1.svg?label=Buy%20me%20a%20coffee&message=🥨&color=black&logo=buy%20me%20a%20coffee&logoColor=white&labelColor=6f4e37)](https://www.buymeacoffee.com/fondberg)

# Easee EV charger component for Home Assistant

Custom component to support Easee EV chargers.

The status sensor is the default sensor and has the following values

```
STANDBY
PAUSED
CHARGING
READY_TO_CHARGE
CAR_CONNECTED
```

**_Important_**
This component quite new and uses the (easee library)[https://github.com/fondberg/easee].
Please help me test and preferbly suggest the fixes as a PR or technical note in an issue.

## Installation

There are 2 different methods of installing the custom component

### HACS installation

_While this component can be installed by HACS, it is not included in the default repository of HACS._

1. Add this repository as a custom repository inside HACS settings. Make sure you select `Integration` as Category.
2. Install the component from the Overview page.

### Git installation

1. Make sure you have git installed on your machine.
2. Navigate to you home assistant configuration folder.
3. Create a `custom_components` folder of it does not exist, navigate down into it after creation.
4. Execute the following command: `git clone https://github.com/fondberg/easee_hass.git easee`
5. Run `bash links.sh`

## Configuration

Add the following to your configuration. Note that username is the phonenumber including the countrycode. It needs to be a + and can't be double zero.

```yaml
sensor:
  - platform: easee
    username: "+46111111111"
    password: <password>
    monitored_conditions:
      - status
      - total_power
      - session_energy
      - energy_per_hour
      - online
      - cable_locked
      - phase_mode
      - current_firmware
      - latest_firmware
    measured_consumption_days:
      - 1
      - 30
      - 365
```
