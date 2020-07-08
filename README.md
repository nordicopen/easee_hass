![Maintenance](https://img.shields.io/maintenance/yes/2020.svg)

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
This component under heavy development and things will most likely change.
Please help me test and preferbly suggest the fixes as a PR or technical note in an issue.

## Installation

Copy all files from `custom_components/easee/` to `custom_components/easee/` inside your config Home Assistant directory.
Or do a a git clone in the custom_components directory and run `bash links.sh`

## Configuration

Add the following to your configuration. Note that username is the phonenumber including the countrycode. It needs to be a + and can't be double zero.

```
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
