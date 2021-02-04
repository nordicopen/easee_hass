[![easee_hass](https://img.shields.io/github/release/fondberg/easee_hass.svg?1)](https://github.com/fondberg/easee_hass) [![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs) ![Validate with hassfest](https://github.com/fondberg/easee_hass/workflows/Validate%20with%20hassfest/badge.svg) ![Maintenance](https://img.shields.io/maintenance/yes/2021.svg)

[![Buy me a coffee](https://img.shields.io/static/v1.svg?label=Buy%20me%20a%20coffee&message=🥨&color=black&logo=buy%20me%20a%20coffee&logoColor=white&labelColor=6f4e37)](https://www.buymeacoffee.com/fondberg)

# Easee EV charger component for Home Assistant

{% if pending_update %}
## New version is available
{% endif %}
{% if prerelease %}
### NB!: This is a Beta version!
{% endif %}

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
This component quite new and uses the [pyease library](https://github.com/fondberg/pyeasee).
Please help me test and preferbly suggest the fixes as a PR or technical note in an issue.

## Configuration

Configuration is done through in Configuration > Integrations where you first configure it and then set the options for what you want to monitor.

For full configuration documentation see [README](https://github.com/fondberg/easee_hass)

