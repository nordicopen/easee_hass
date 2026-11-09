"""Which RFID cards may charge: the whitelist from the integration options.

The whitelist is read live from the config entry, so editing it needs no reload.
A learning mode accepts the next unknown card and adds it to the whitelist, which
replaces pairing a card in the Easee app (the cloud API offers no card list, and
with OCPP active the charger asks Home Assistant, not the app).
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import CONF_ALLOWED_ID_TAGS, EVENT_OCPP_AUTHORIZE
from .models import IdTag, Serial

_LOGGER = logging.getLogger(__name__)

LEARNING_WINDOW = timedelta(minutes=2)
# RemoteStartTransaction from Home Assistant uses this tag; it is always accepted.
REMOTE_START_ID_TAG = "HOMEASSISTANT"
LEARNED_NOTIFICATION_ID = "easee_ocpp_rfid_learned"


def normalised_id_tag(id_tag: IdTag) -> str:
    """Compare card ids case-insensitively and without surrounding blanks."""
    return id_tag.strip().upper()


class RfidAuthorizer:
    """Answers the charger's Authorize/StartTransaction requests."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Read the whitelist from this entry's options."""
        self._hass = hass
        self._entry = entry
        self._learning_until: datetime | None = None

    def allowed_id_tags(self) -> list[IdTag]:
        """Return the whitelist as currently configured."""
        tags: list[IdTag] = self._entry.options.get(CONF_ALLOWED_ID_TAGS, [])
        return tags

    def is_on_whitelist(self, id_tag: IdTag) -> bool:
        """Return True if the card is configured."""
        return normalised_id_tag(id_tag) in {
            normalised_id_tag(tag) for tag in self.allowed_id_tags()
        }

    def is_learning(self) -> bool:
        """Return True while the next unknown card will be learned."""
        return (
            self._learning_until is not None and dt_util.utcnow() < self._learning_until
        )

    @callback
    def start_learning(self) -> None:
        """Accept and remember the next unknown card presented within the learning window."""
        self._learning_until = dt_util.utcnow() + LEARNING_WINDOW

    @callback
    def is_allowed(self, serial: Serial, id_tag: IdTag) -> bool:
        """Decide, fire an event for automations, and learn the card if learning is on."""
        is_remote_start = normalised_id_tag(id_tag) == REMOTE_START_ID_TAG
        allowed = is_remote_start or self.is_on_whitelist(id_tag)
        if not allowed and self.is_learning():
            self._learn(serial, id_tag)
            allowed = True
        self._hass.bus.async_fire(
            EVENT_OCPP_AUTHORIZE,
            {"serial": serial, "id_tag": id_tag, "accepted": allowed},
        )
        return allowed

    def _learn(self, serial: Serial, id_tag: IdTag) -> None:
        self._learning_until = None
        options = {
            **self._entry.options,
            CONF_ALLOWED_ID_TAGS: [*self.allowed_id_tags(), id_tag],
        }
        self._hass.config_entries.async_update_entry(self._entry, options=options)
        _LOGGER.info(
            "%s: RFID card %s learned and added to the whitelist", serial, id_tag
        )
        persistent_notification.async_create(
            self._hass,
            f"RFID card {id_tag} (charger {serial}) was added to the OCPP whitelist.",
            title="Easee: RFID card learned",
            notification_id=LEARNED_NOTIFICATION_ID,
        )
