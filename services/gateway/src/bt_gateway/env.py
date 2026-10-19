"""Gateway settings on top of `BaseEnv`."""

from bt.common import BaseEnv
from pydantic import Field


class Env(BaseEnv):
    """The gateway has no database; it needs the access-token secret."""

    # Verifies the 15-minute `bt_access` cookie that auth signs.
    ACCESS_TOKEN_SECRET: str = Field(min_length=32, repr=False)
    # How long one proxied call may take before the caller gets 502.
    UPSTREAM_TIMEOUT_MS: int = Field(default=15_000, gt=0)
    # Per user (signed in) or per IP (otherwise), per minute, over all routes.
    RATE_LIMIT_PER_MINUTE: int = Field(default=300, gt=0)
    # Per IP, per 15 minutes, on each of /auth/login, /auth/2fa/verify, /auth/reset/*.
    RATE_LIMIT_AUTH_PER_15_MIN: int = Field(default=10, gt=0)
    # Per IP, per minute, on /ingest/message (the device token has its own limit inside ingest).
    RATE_LIMIT_INGEST_PER_MINUTE: int = Field(default=60, gt=0)
    # Per IP, per minute, on /telegram/webhook/*.
    RATE_LIMIT_WEBHOOK_PER_MINUTE: int = Field(default=120, gt=0)
