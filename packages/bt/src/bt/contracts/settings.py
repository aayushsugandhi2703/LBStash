"""`GET|PATCH /settings` is composed by the gateway. Each field belongs to one service (ledger, planning, telegram); a PATCH is split by field to its owner."""

from typing import Literal

from .base import Int, Model, TimeStr
from .ledger import LedgerSettings, LedgerSettingsPatch
from .planning import PlanningSettings, PlanningSettingsPatch
from .telegram import TelegramSettings, TelegramSettingsPatch


# Bases are listed in reverse because pydantic collects fields last-to-first (key order: ledger, planning, telegram, currency).
class SettingsDto(TelegramSettings, PlanningSettings, LedgerSettings):
    currency: Literal['INR']


class SettingsPatch(TelegramSettingsPatch, PlanningSettingsPatch, LedgerSettingsPatch):  # type: ignore[misc,valid-type]
    pass


class MeDto(Model):
    """`GET /me`: what the shared header needs. Composed by the gateway."""

    id: str
    email: str
    name: str | None
    timezone: str
    pending_email: str | None
    delete_after: TimeStr | None
    # unread limit alerts + messages that need a look, for the nav badge and the Account menu
    alert_badge_count: Int
    needs_look_count: Int
    untagged_count: Int
