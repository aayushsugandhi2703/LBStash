"""Shared building blocks: money is integer paise, times are ISO strings, days are 'YYYY-MM-DD'."""

from typing import Any, Literal

from .base import (
    Bool,
    IsoDateTime,
    Model,
    OptNull,
    PositivePaise,
    TxSource,
    TxStatus,
    TxType,
    Uuid,
)


class TransactionDto(Model):
    id: Uuid
    type: TxType
    amount_minor: PositivePaise
    # When the payment happened (read from the bank message when there is one).
    occurred_at: IsoDateTime
    payee: str | None
    description: str | None
    category_id: Uuid | None
    category_name: str | None
    source: TxSource
    status: TxStatus
    recurring_id: Uuid | None
    # When the Shortcut delivered it (captured rows only).
    captured_at: IsoDateTime | None
    # Amount and direction were read but nothing else (README 4.7).
    weak_parse: Bool


class CategoryDto(Model):
    id: Uuid
    # Stored lowercase; show with `display_tag`.
    name: str
    archived: Bool


class Empty(Model):
    pass


class Ok(Model):
    ok: Literal[True]


class ErrorDetail(Model):
    code: str
    message: str
    details: OptNull[Any] = None


class ErrorBody(Model):
    """Error body every service returns (see `AppError.to_json`)."""

    error: ErrorDetail


class ExportPart(Model):
    """`GET /internal/export`: a data service's rows for the user, secrets left out. Auth composes the parts into the export."""

    service: str
    tables: dict[str, list[dict[str, Any]]]

