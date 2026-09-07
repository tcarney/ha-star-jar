"""Constants for star_jar."""

from __future__ import annotations

from enum import StrEnum
from logging import Logger, getLogger

from homeassistant.const import Platform

LOGGER: Logger = getLogger(__package__)

DOMAIN = "star_jar"
PLATFORMS: list[Platform] = [Platform.SENSOR]

# The Lovelace card, served from the integration's own www directory.
CARD_JS = "star-jar-card.js"
CARD_URL_PATH = f"/{DOMAIN}/{CARD_JS}"

# Config entry data.
CONF_CHILD_NAME = "child_name"

# Config entry options, editable after setup.
CONF_JAR_SIZE = "jar_size"
CONF_AI_TASK_ENTITY = "ai_task_entity"
CONF_INSTRUCTIONS = "instructions"

DEFAULT_JAR_SIZE = 24
DEFAULT_INSTRUCTIONS = (
    "You write one short, warm sentence to a nine-year-old about a star she just earned or spent. "
    "Be specific about the reason. Use only the numbers you are given. No emoji."
)

STORAGE_VERSION = 1
LEDGER_LIMIT = 1000
RECENT_LIMIT = 10
NARRATION_TIMEOUT = 30
MAX_STARS_PER_AWARD = 10
MAX_ADJUST = 100

EVENT_UPDATED = "star_jar_updated"

SERVICE_AWARD = "award"
SERVICE_ADJUST = "adjust"
SERVICE_REDEEM = "redeem"
DEFAULT_ADJUST_SOURCE = "adjust"

# Service fields, event payload keys and sensor attribute keys share one vocabulary.
ATTR_ACTION = "action"
ATTR_AT = "at"
ATTR_JAR = "jar"
ATTR_JAR_BEFORE = "jar_before"
ATTR_JAR_FILLED = "jar_filled"
ATTR_JAR_SIZE = "jar_size"
ATTR_LAST_EVENT = "last_event"
ATTR_MESSAGE = "message"
ATTR_REASON = "reason"
ATTR_RECENT = "recent"
ATTR_REWARD = "reward"
ATTR_REWARDS_AVAILABLE = "rewards_available"
ATTR_SOURCE = "source"
ATTR_STARS = "stars"
ATTR_STARS_TO_FILL = "stars_to_fill"
ATTR_STARS_TODAY = "stars_today"


class JarAction(StrEnum):
    """What a ledger entry records."""

    AWARD = "award"
    ADJUST = "adjust"
    REDEEM = "redeem"
