# Running the tests

Use Linux and Python 3.14, matching the Home Assistant test environment:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-test.txt
pytest -q tests --timeout=60
```

The pinned `pytest-homeassistant-custom-component` package supplies Home Assistant
2026.10.4 and its matching pytest dependencies. The tests run the integration with
a simulated Easee cloud and OCPP chargers; no account or hardware is required.
Keep the plugin's Home Assistant pin: overriding it with 2026.11.1 currently fails
before test collection because the plugin imports removed logger helpers.

Coverage includes setup and rollback, entities and commands, reconnect races,
connection cleanup, repair detection, diagnostic redaction, malformed inputs and
cloud failures. They do not replace validation against real charger firmware.

CI also runs `hassfest`, HACS validation, flake8 and ruff. The autolabeler uses
`pull_request_target` for fork PRs without checking out or executing PR code.
That event starts using the updated workflow after it reaches the base branch;
the read-only `pull_request` run skips labeling for forks.
