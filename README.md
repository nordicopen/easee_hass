[![easee_hass](https://img.shields.io/github/release/fondberg/easee_hass.svg?1)](https://github.com/fondberg/easee_hass) [![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs) ![Validate with hassfest](https://github.com/fondberg/easee_hass/workflows/Validate%20with%20hassfest/badge.svg) ![Maintenance](https://img.shields.io/maintenance/yes/2022.svg) [![Easee_downloads](https://img.shields.io/github/downloads/fondberg/easee_hass/total)](https://github.com/fondberg/easee_hass)

[![Buy me a coffee](https://img.shields.io/static/v1.svg?label=Buy%20me%20a%20coffee&message=🥨&color=black&logo=buy%20me%20a%20coffee&logoColor=white&labelColor=6f4e37)](https://www.buymeacoffee.com/fondberg)

# Easee EV charger component for Home Assistant

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

## Installation

There are 2 different methods of installing the custom component

### HACS installation

1. Add this repository from HACS->Integrations.
2. Restart Home Assistant.
3. Install the component from the Configuration->Integrations.

### Git installation

1. Make sure you have git installed on your machine.
2. Navigate to you home assistant configuration folder.
3. Create a `custom_components` folder of it does not exist, navigate down into it after creation.
4. Execute the following command: `git clone https://github.com/fondberg/easee_hass.git easee`
5. Run `bash links.sh`

## Configuration

Configuration is done through in Configuration > Integrations where you first configure it and then set the options for what you want to monitor.

## Development

This project uses `black` for code formatting and `flake8` for linting.
Always run

```
make lint
```

Before pushing your changes
