![Maintenance](https://img.shields.io/maintenance/yes/2020.svg)

[![Buy me a coffee](https://img.shields.io/static/v1.svg?label=Buy%20me%20a%20coffee&message=🥨&color=black&logo=buy%20me%20a%20coffee&logoColor=white&labelColor=6f4e37)](https://www.buymeacoffee.com/fondberg)

# Easee EV charger component for Home Assistant

Custom component to support Easee EV chargers. Currently it has a sensor per charger with the following values

```
STANDBY
PAUSED
CHARGING
READY_TO_CHARGE
CAR_CONNECTED
```

The attributes for each sensor has the following:

```
id: EH1111111
name: Easee Home 11111
total_energy: 0
energy_hour: 0
session_energy: 1.48181
smart_charging: false
cable_locked: true
latest_pulse: 2020-07-04T12:21:49Z
firmware: 230
latest_firmware: 230
node_type: Master
phase_mode: Auto
consumption_1_day: 4.660419
consumption_30_days: 157.659282
consumption_365_days: 555.8552820000001
friendly_name: easee_charger_EH239897
icon: mdi:flash
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
```
