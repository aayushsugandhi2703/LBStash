"""`GET|PATCH /settings` is composed by the gateway. Each field belongs to one service (transactions, planning, telegram); a PATCH is split by field to its owner."""

from typing import Literal

from .base import Int, Model, TimeStr
from .planning import PlanningSettings, PlanningSettingsPatch
from .telegram import TelegramSettings, TelegramSettingsPatch
from .transactions import TransactionSettings, TransactionSettingsPatch


# Bases are listed in reverse because pydantic collects fields last-to-first (key order: transactions, planning, telegram, currency).
class SettingsDto(TelegramSettings, PlanningSettings, TransactionSettings):
    currency: Literal['INR']


class SettingsPatch(TelegramSettingsPatch, PlanningSettingsPatch, TransactionSettingsPatch):  # type: ignore[misc,valid-type]
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
