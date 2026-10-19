"""Ingest service contracts: devices (hashed tokens), nonces, the parser, unparsed messages (encrypted, 30 days). A parsed message is never stored."""

from typing import Annotated, Literal, get_args

from pydantic import Field, StringConstraints

from .base import (
    Bool,
    Int,
    IsoDateTime,
    Model,
    Opt,
    OptNull,
    Paise,
    PositivePaise,
    SixDigits,
    TxStatus,
    TxType,
    Uuid,
)
from .common import TransactionDto
from .ledger import IngestOutcome


class IngestBody(Model):
    # Empty = the sender was run by hand (no message): the server records it as the device test and stores nothing.
    text: Annotated[str, StringConstraints(max_length=2000)]
    received_at: IsoDateTime
    nonce: Annotated[str, StringConstraints(min_length=8, max_length=128)]
    # Optional sender id of the SMS (for example `AX-HDFCBK`). Only used when the device has a sender allow-list.
    sender: Opt[Annotated[str, StringConstraints(min_length=1, max_length=32)]] = None


class IngestMessageTx(Model):
    id: Uuid
    type: TxType
    amount_minor: PositivePaise
    status: TxStatus


class IngestMessageRes(Model):
    """`POST /ingest/message`: 201 created or saved_as_credit; 200 any other ledger answer or `test` (never stored); 202 `ignored` (OTP, promo, not a payment, sender not allowed)."""

    outcome: Literal[(*get_args(IngestOutcome), 'ignored', 'test')]
    transaction: IngestMessageTx | None
    # Set when outcome is `ignored`.
    reason: Opt[Literal['otp_or_promo', 'not_a_transaction', 'sender_not_allowed']] = None


class DeviceLastTest(Model):
    at: IsoDateTime
    source: Literal['device', 'web']
    delay_seconds: Int | None
    amount_minor: Paise | None


class DeviceDto(Model):
    id: Uuid
    name: str
    last_seen_at: IsoDateTime | None
    revoked_at: IsoDateTime | None
    created_at: IsoDateTime
    # Masked token for display, for example `ledg_live_8f3a...b605`. The token itself is never readable again.
    token_hint: str
    # When the token was last replaced (None = never rotated).
    rotated_at: IsoDateTime | None
    # Seconds between the time written in the last message and the moment the sender ran (None when unknown).
    last_delay_seconds: Int | None
    # Empty list = every sender is accepted.
    allowed_senders: list[str]
    # The latest test message (from the phone or from the Devices page), for the live test status.
    last_test: DeviceLastTest | None


class DevicesRes(Model):
    devices: list[DeviceDto]


SenderList = Annotated[
    list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=32)]],
    Field(max_length=20),
]
DeviceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class CreateDeviceReq(Model):
    """`POST /devices`: first token, or a new one for the active device (rotate, needs `code`)."""

    name: Opt[DeviceName] = None
    code: Opt[SixDigits] = None
    # Rotate this device. Omitted: the user's active device is rotated, or a first one is created.
    device_id: Opt[Uuid] = None
    allowed_senders: Opt[SenderList] = None


class DeviceTokenRes(Model):
    """The only time the token is shown."""

    device: DeviceDto
    token: str
    rotated: Bool


class RevokeDeviceReq(Model):
    """`DELETE /devices/:id` (body, or `x-totp-code` header)."""

    code: Opt[SixDigits] = None


class RevokeDeviceRes(Model):
    device: DeviceDto


class PatchDeviceReq(Model):
    name: Opt[DeviceName] = None
    allowed_senders: Opt[SenderList] = None


class TestDeviceRes(Model):
    """`POST /devices/test`: the server runs a test message through the parser for the active device; never touches the ledger."""

    __test__ = False  # not a pytest class, despite the name

    ok: Literal[True]
    device: DeviceDto
    amount_minor: PositivePaise
    type: TxType


class UnparsedSuggestion(Model):
    """What the parser could still guess, to prefill the form."""

    type: TxType | None
    amount_minor: PositivePaise | None
    payee: str | None


class UnparsedDto(Model):
    """One "Needs a look" message. `text` is the user's own message (masked), decrypted only for this response."""

    id: Uuid
    received_at: IsoDateTime
    expires_at: IsoDateTime
    reason: Literal['no_amount', 'direction_unclear', 'unreadable']
    text: str
    suggestion: UnparsedSuggestion


class UnparsedRes(Model):
    items: list[UnparsedDto]
    open: Int


class ResolveUnparsedReq(Model):
    type: TxType
    amount_minor: PositivePaise
    payee: OptNull[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None


class ResolveUnparsedRes(Model):
    transaction: TransactionDto
    open: Int


class DismissUnparsedRes(Model):
    ok: Literal[True]
    open: Int


class UnparsedCountRes(Model):
    """Internal: `GET /internal/unparsed/count`: number of open Needs-a-look messages (header badge, dashboard)."""

    open: Int

