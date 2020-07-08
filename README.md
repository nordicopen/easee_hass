# Custom component for Easee EV charger in Home-Assistant

## Setup

### Minimal

```
sensor:
  - platform: easee
    username: "+46111111111"
    password: <password>
```

### Full

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
