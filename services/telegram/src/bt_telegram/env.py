"""Telegram settings on top of the shared ones. The shared `FIELD_KEY` encrypts the bot token; `PUBLIC_URL` is the webhook base."""

from bt.common import BaseEnv
from pydantic import Field


class Env(BaseEnv):
    # Tests point this at a fake server.
    TELEGRAM_API_BASE: str = 'https://api.telegram.org'
    # Gap between two messages to the same chat (Telegram allows about one per second).
    TELEGRAM_SEND_GAP_MS: int = Field(default=1100, ge=0)
