[![easee_hass](https://img.shields.io/github/release/nordicopen/easee_hass.svg?1)](https://github.com/nordicopen/easee_hass) [![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs) ![Validate with hassfest](https://github.com/nordicopen/easee_hass/workflows/Validate%20with%20hassfest/badge.svg) ![Maintenance](https://img.shields.io/maintenance/yes/2024.svg) [![Easee_downloads](https://img.shields.io/github/downloads/nordicopen/easee_hass/total)](https://github.com/nordicopen/easee_hass)



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
disconnected
awaiting_start
charging
ready_to_charge
completed
error
```

**_Important_**
This component uses the [pyease library](https://github.com/nordicopen/pyeasee).
Suggestions for improvements are welcome. So are PRs.

## Configuration

Configuration is done through in Configuration > Integrations where you first configure it and then set the options for what you want to monitor.

For full configuration documentation see [README](https://github.com/nordicopen/easee_hass)
