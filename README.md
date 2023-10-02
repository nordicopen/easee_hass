[![easee_hass](https://img.shields.io/github/release/fondberg/easee_hass.svg?1)](https://github.com/fondberg/easee_hass) [![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration) ![Validate with hassfest](https://github.com/fondberg/easee_hass/workflows/Validate%20with%20hassfest/badge.svg) ![Maintenance](https://img.shields.io/maintenance/yes/2023.svg) [![Easee_downloads](https://img.shields.io/github/downloads/fondberg/easee_hass/total)](https://github.com/fondberg/easee_hass) [![easee_hass_downloads](https://img.shields.io/github/downloads/fondberg/easee_hass/latest/total)](https://github.com/fondberg/easee_hass)

[![Buy me a coffee](https://img.shields.io/static/v1.svg?label=Buy%20me%20a%20coffee&message=🥨&color=black&logo=buy%20me%20a%20coffee&logoColor=white&labelColor=6f4e37)](https://www.buymeacoffee.com/fondberg)

# Easee EV charger component for Home Assistant

Custom component to support Easee EV chargers and equalizers.

The status sensor is the default sensor and has the following values

```
disconnected
awaiting_start
charging
ready_to_charge
completed
error
```
Some of the other non-common sensors like Current and Voltage are disabled by default (shown as "unavailable"). They can be enabled in the HA GUI via Integrations->[Easee Name]->Devices->[Easee Equilizer Name] and under Diagnostic click on Current/Voltage->gear_icon and then Enable it. Each of these sensors has also attributes which contain values like current and voltage per phase. See [#271](https://github.com/fondberg/easee_hass/issues/271) on how to use these attributes.

## Installation

There are 2 different methods of installing the custom component

### HACS installation

1. Add this repository from HACS->Integrations.
2. Restart Home Assistant.
3. Install the component from Settings->Integrations. You may have to clear the browser cache to make the Easee integration appear in the list.

### Git installation

1. Make sure you have git installed on your machine.
2. Navigate to you home assistant configuration folder.
3. Create a `custom_components` folder of it does not exist, navigate down into it after creation.
4. Execute the following command: `git clone https://github.com/fondberg/easee_hass.git easee`
5. Run `bash links.sh`

## Monitored chargers/equalizers

Since v0.9.47 the integration only includes the chargers and equalizers that has been added to the Easee official app, rather than showing all that are available to the logged in user. This change was done becuase in larger installations there could be 10s or 100s of chargers listed which in most cases does not make much sense.
So if you do not see all your products in the integration, open the official app and make sure they are listed there first.

## Configuration

Configuration is done through in Configuration > Integrations where you first configure it and then set the options for what you want to monitor.

## Use
The basic use of the integrations from the UI should be self-explanatory. The integration defines a number of services that can be used from automations and scripts to control the charger and the charging process. The available services can be found in Home Assistant at Developer tools->Services.

The easiest way to set up services and their parameters is to use the automation editor or the developer tools. However, you can also write the code in plain yaml. The UI will use device_id as target for the services. This is a random string generated internally by HA and is not very user friendly. To simplify for hard-core coders and to be backward compatible with previous versions of this integration you can also use charger_id or circuit_id as targets.
Three examples that will do the same thing:
```yaml
service: easee.set_circuit_dynamic_limit
data:
  device_id: b40f1f45d28b0891
  currentP1: 10
```
```yaml
service: easee.set_circuit_dynamic_limit
data:
  charger_id: EVK1234
  currentP1: 10
```
```yaml
service: easee.set_circuit_dynamic_limit
data:
  circuit_id: 30456
  currentP1: 10
```
For details on the Easee API, please refer to https://developer.easee.cloud/reference

## Debug logging
A full debug log can be enabled by entering following into `configuration.yaml` and restarting Home Assistant
```yaml
logger:
  default: info
  logs:
    pyeasee: debug
    custom_components.easee: debug
```

## Development Container
One option for development is to use the VS Code Dev Container. You need to have Docker installed.

1. Open a new blank vscode
1. Select Command palette->Dev containers: Clone repository in named container volume
1. Follow the prompts
1. Wait for the container to be built.
1. Press `Ctrl`+`Shift`+`P` and select `Tasks: Run Task` > `Run Home Assistant on port 9125`.
1. Wait for Home Assistant to start and go to http://localhost:9125/.
1. Walk through the Home Assistant first-launch UI.
1. Go to http://localhost:9125/config/integrations, click `Add Integration` and add the `Easee` integration.
1. To debug, press `F5` to attach to the Home Assistant running in the container.


Always run
```console
$ make lint
```
before pushing your changes.

## Translation
To handle submission of translations we are using [Lokalise](https://lokalise.com/login/). They provide us with an amazing platform that is easy to use and maintain.

To help out with the translation of Miele integration  you need an account on Lokalise, the easiest way to get one is to [click here](https://lokalise.com/login/)  then select "Log in with GitHub".

When you have created the account, the [click here](https://app.lokalise.com/public/50153460650965e9a01e21.29484567/) to join the project. If you want to add a new language, please open an issue.

The translations are pulled when a new release of the integration is prepared. So you must wait until there is a new release until your look for your updates.

If you want to add new elements that needs translation you should enter them in /translations/en.json and submit a PR. The new keys will appear in Lokalise when the PR is merged.

## Support and cooperation
This project is supported by

[<img src="https://raw.githubusercontent.com/astrandb/documents/fef0776bbb7924e0253b9755d7928631fb19d5c7/img/Lokalise_logo_colour_black_text.svg" width=120>](https://lokalise.com)
