"""Ingest settings on top of the shared ones. The shared `FIELD_KEY` encrypts unreadable messages."""

from bt.common import BaseEnv
from pydantic import Field


class Env(BaseEnv):
    # Messages per minute per device / per client address.
    INGEST_RATE_PER_DEVICE_MIN: int = Field(default=20, gt=0)
    INGEST_RATE_PER_IP_MIN: int = Field(default=60, gt=0)
    # Failed token checks per minute per address before 429.
    INGEST_BAD_TOKEN_PER_IP_MIN: int = Field(default=10, gt=0)
