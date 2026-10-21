"""Contract tests (port of `packages/contracts`).

`CORPUS` holds the output of the TypeScript Zod schemas on each input: the exact JSON `Schema.parse` printed ('same' = unchanged), or the issue paths Zod reported. The Python models must give the same camelCase JSON or fail on the same paths. Times compare as instants (Zod echoed the input string; the models normalise to `...mmmZ`).
"""

import json
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, get_args

import lbstash.contracts as C
import pytest
from lbstash.contracts.base import (
    CoerceInt,
    IsoDateTime,
    Paise,
    PositivePaise,
    StringBool,
    Uuid,
    dump,
    iso_ms,
    patch_keys,
    validation_details,
)
from pydantic import BaseModel, TypeAdapter, ValidationError

U1 = '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'
U2 = '7c9e6679-7425-40de-944b-e07fc1f90ae7'
T1 = '2025-03-14T10:30:00.000Z'

CORPUS: list[tuple[str, Any, Any]] = [
    ('TransactionDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, 'same'),
    ('TransactionDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 0, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, ['amountMinor']),
    ('TransactionDto', {'id': 'nope', 'type': 'x', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, ['id', 'type']),
    ('TransactionDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False, 'extra': 1}, {'ok': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}}),
    ('TransactionDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, ['payee']),
    ('TransactionDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, ['occurredAt']),
    ('TransactionDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 9007199254740992, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, ['amountMinor']),
    ('TransactionDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 12.5, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, ['amountMinor']),
    ('TransactionDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': '5', 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, ['amountMinor']),
    ('TransactionDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': 'no'}, ['weakParse']),
    ('CategoryDto', {'id': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'name': 'food', 'archived': False}, 'same'),
    ('CategoryDto', {'id': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'name': 'food', 'archived': 1}, ['archived']),
    ('Ok', {'ok': True}, 'same'),
    ('Ok', {'ok': False}, ['ok']),
    ('Empty', {'a': 1}, {'ok': {}}),
    ('ErrorBody', {'error': {'code': 'x', 'message': 'm'}}, 'same'),
    ('ErrorBody', {'error': {'code': 'x', 'message': 'm', 'details': {'a': 'b'}}}, 'same'),
    ('ExportPart', {'service': 'transactions', 'tables': {'t': [{'a': 1, 'b': None}]}}, 'same'),
    ('ExportPart', {'service': 'transactions', 'tables': {'t': [1]}}, ['tables.t.0']),
    ('UserDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'email': 'a@b.in', 'name': None, 'timezone': 'Asia/Kolkata', 'pendingEmail': None, 'deleteAfter': None}, 'same'),
    ('UserDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'email': 'a@b.in', 'name': None, 'timezone': 'Asia/Kolkata', 'pendingEmail': None, 'deleteAfter': None, 'createdAt': '2025-01-01T00:00:00Z'}, 'same'),
    ('UserDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'email': 'a@b.in', 'name': None, 'timezone': '', 'pendingEmail': None, 'deleteAfter': None}, ['timezone']),
    ('UserDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'email': 'a@b.in', 'name': None, 'timezone': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'pendingEmail': None, 'deleteAfter': None}, ['timezone']),
    ('VerifyTotpReq', {'code': '123456'}, 'same'),
    ('VerifyTotpReq', {'code': '12345'}, ['code']),
    ('VerifyTotpReq', {'code': '12345a'}, ['code']),
    ('SessionCheckRes', {'valid': True}, {'ok': {'valid': True, 'limited': False}}),
    ('SessionCheckRes', {'valid': True, 'limited': True}, 'same'),
    ('SessionCheckReq', {'sid': 'x'}, ['sid']),
    ('EmailInput', ' Foo@Bar.COM ', {'ok': 'foo@bar.com'}),
    ('EmailInput', 'nope', ['']),
    ('EmailInput', 'a@b', ['']),
    ('EmailInput', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@b.co', ['']),
    ('EmailInput', 'john.doe+tag@sub.example.org', 'same'),
    ('RegisterReq', {'email': ' A@B.IN ', 'password': 'x', 'name': '  Asha ', 'timezone': 'Asia/Kolkata'}, {'ok': {'email': 'a@b.in', 'password': 'x', 'name': 'Asha', 'timezone': 'Asia/Kolkata'}}),
    ('RegisterReq', {'email': 'a@b.in', 'password': ''}, ['password']),
    ('RegisterReq', {'email': 'a@b.in', 'password': 'x', 'name': '   '}, ['name']),
    ('RegisterReq', {'email': 'a@b.in', 'password': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}, ['password']),
    ('LoginReq', {'email': 'x'}, ['email', 'password']),
    ('LoginReq', {'email': 'Q@R.IO', 'password': 'p'}, {'ok': {'email': 'q@r.io', 'password': 'p'}}),
    ('LoginRes', {'twoFactorToken': None, 'methods': ['totp', 'passkey'], 'setupRequired': True, 'setup': {'totpEnabled': True, 'recoveryCodes': False, 'complete': False}}, 'same'),
    ('LoginRes', {'twoFactorToken': 't', 'methods': ['sms'], 'setupRequired': False, 'setup': None}, ['methods.0']),
    ('TwoFactorVerifyReq', {'twoFactorToken': 'tokentokentoken', 'code': '123456'}, 'same'),
    ('TwoFactorVerifyReq', {'twoFactorToken': 'tokentokentoken'}, ['']),
    ('TwoFactorVerifyReq', {'twoFactorToken': 'tokentokentoken', 'code': '123456', 'recoveryCode': 'abcd-efgh-i'}, ['']),
    ('TwoFactorVerifyReq', {'twoFactorToken': 'tokentokentoken', 'passkey': {'id': 'x'}}, 'same'),
    ('TwoFactorVerifyReq', {'twoFactorToken': 'tokentokentoken', 'recoveryCode': '  abcd-efgh-ij  '}, {'ok': {'twoFactorToken': 'tokentokentoken', 'recoveryCode': 'abcd-efgh-ij'}}),
    ('TwoFactorVerifyReq', {'twoFactorToken': 'short', 'code': '12'}, ['code', 'twoFactorToken']),
    ('TwoFactorVerifyReq', {'twoFactorToken': 'tokentokentoken', 'recoveryCode': 'short'}, ['recoveryCode']),
    ('TwoFactorEnableStartReq', {}, 'same'),
    ('TwoFactorEnableStartReq', {'currentCode': '1'}, ['currentCode']),
    ('TwoFactorEnableConfirmReq', {'code': '123456'}, 'same'),
    ('TwoFactorEnableStartRes', {'secret': 'S', 'otpauthUri': 'otpauth://x'}, 'same'),
    ('RecoveryCodesReq', {}, 'same'),
    ('RecoveryCodesRes', {'codes': ['a', 'b'], 'remaining': 2, 'setup': {'totpEnabled': True, 'recoveryCodes': False, 'complete': False}}, 'same'),
    ('AuthSessionRes', {'user': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'email': 'a@b.in', 'name': None, 'timezone': 'Asia/Kolkata', 'pendingEmail': None, 'deleteAfter': None}, 'setup': {'totpEnabled': True, 'recoveryCodes': False, 'complete': False}, 'recoveryCodesLeft': 10, 'recoveryCodeUsed': False, 'deletionCancelled': False}, 'same'),
    ('AuthSessionRes', {'user': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'email': 'a@b.in', 'name': None, 'timezone': 'Asia/Kolkata', 'pendingEmail': None, 'deleteAfter': None}, 'setup': {'totpEnabled': True, 'recoveryCodes': False, 'complete': False}, 'recoveryCodesLeft': 1.5, 'recoveryCodeUsed': False, 'deletionCancelled': False}, ['recoveryCodesLeft']),
    ('FactorsRes', {'totp': {'enabled': True, 'since': None}, 'passkeys': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'label': 'Mac', 'createdAt': '2025-01-01T00:00:00Z', 'lastUsedAt': None}], 'recoveryCodes': {'remaining': 3, 'total': 10}, 'passwordChangedAt': '2025-01-01T00:00:00Z', 'setup': {'totpEnabled': True, 'recoveryCodes': False, 'complete': False}}, 'same'),
    ('PasswordChangeReq', {'currentPassword': 'a', 'newPassword': 'b', 'code': '123456'}, 'same'),
    ('PasswordChangeReq', {'currentPassword': 'a', 'newPassword': 'b', 'code': '12345'}, ['code']),
    ('PasswordChangeRes', {'ok': True, 'signedOutOthers': 2}, 'same'),
    ('PasskeyRegisterVerifyReq', {'response': {'a': 1}, 'label': ' Mac '}, {'ok': {'response': {'a': 1}, 'label': 'Mac'}}),
    ('PasskeyRegisterVerifyReq', {'response': 'x'}, ['response']),
    ('PasskeyRegisterVerifyReq', {'response': {}, 'label': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}, ['label']),
    ('PasskeyLoginOptionsReq', {'twoFactorToken': 'tokentokentoken'}, 'same'),
    ('PasskeyLoginVerifyReq', {'twoFactorToken': 'tokentokentoken', 'response': {}}, 'same'),
    ('SessionsRes', {'sessions': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'device': 'Mac', 'ip': None, 'createdAt': 'a', 'lastActiveAt': 'b', 'current': True}]}, 'same'),
    ('RevokeSessionsRes', {'revoked': 2}, 'same'),
    ('AuditQuery', {}, {'ok': {'limit': 50}}),
    ('AuditQuery', {'limit': '25'}, {'ok': {'limit': 25}}),
    ('AuditQuery', {'limit': '0'}, ['limit']),
    ('AuditQuery', {'limit': '201'}, ['limit']),
    ('AuditQuery', {'limit': 'x'}, ['limit']),
    ('AuditQuery', {'limit': '1.5'}, ['limit']),
    ('AuditQuery', {'limit': ''}, ['limit']),
    ('AuditRes', {'entries': [{'id': 1, 'at': '2025-01-01T00:00:00Z', 'action': 'login.ok', 'ip': '1.2.3.4', 'deviceId': None, 'meta': {'a': [1]}}]}, 'same'),
    ('AuditRes', {'entries': [{'id': 1.5, 'at': 'x', 'action': 'a', 'ip': None, 'deviceId': None, 'meta': None}]}, ['entries.0.id']),
    ('UpdateMeReq', {'name': '  Asha  '}, {'ok': {'name': 'Asha'}}),
    ('UpdateMeReq', {'name': ''}, 'same'),
    ('UpdateMeReq', {'name': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}, ['name']),
    ('ChangeEmailReq', {'newEmail': ' X@Y.CO ', 'code': '123456'}, {'ok': {'newEmail': 'x@y.co', 'code': '123456'}}),
    ('ChangeEmailReq', {'newEmail': 'x', 'code': '1'}, ['code', 'newEmail']),
    ('ConfirmEmailReq', {'token': 'short'}, ['token']),
    ('ExportReq', {'code': '123456'}, 'same'),
    ('ExportRes', {'exportedAt': '2025-03-14T16:00:00+05:30', 'filename': 'f.json', 'entries': 3, 'parts': [{'service': 'auth', 'tables': {}}]}, 'same'),
    ('DeleteAccountReq', {'confirm': 'DELETE', 'code': '123456'}, 'same'),
    ('DeleteAccountReq', {'confirm': 'delete', 'code': '123456'}, ['confirm']),
    ('DeleteAccountRes', {'deleteAfter': '2025-03-14T10:30:00.000Z'}, 'same'),
    ('ResetVerifyReq', {'email': ' A@B.IN ', 'recoveryCode': ' abcdefghij '}, {'ok': {'email': 'a@b.in', 'recoveryCode': 'abcdefghij'}}),
    ('ResetVerifyReq', {'email': 'x', 'recoveryCode': 'a'}, ['email', 'recoveryCode']),
    ('ResetCompleteReq', {'resetToken': 'tokentokentoken', 'newPassword': 'pw'}, 'same'),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-03-14T16:00:00+05:30', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': 'k1'}, {'ok': {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-03-14T16:00:00+05:30', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'weakParse': False, 'reversal': False, 'dedupeKey': 'k1'}}),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-03-14T16:00:00+05:30', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': 'k1', 'payee': None, 'reference': 'r', 'accountLast4': '1234', 'balanceAfterMinor': -5, 'weakParse': True, 'reversal': True}, 'same'),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-03-14T16:00:00+05:30', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': 'k1', 'accountLast4': '12345'}, ['accountLast4']),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-03-14T16:00:00+05:30', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': 'k1', 'payee': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}, ['payee']),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-03-14T16:00:00+05:30', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': ''}, ['dedupeKey']),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': -1, 'occurredAt': '2025-03-14T16:00:00+05:30', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': 'k1'}, ['amountMinor']),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-03-14T10:30:00', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': 'k1'}, ['occurredAt']),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-02-30T10:30:00Z', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': 'k1'}, ['occurredAt']),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-03-14T16:00:00+05:30', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': 'k1', 'weakParse': None}, ['weakParse']),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-03-14T10:30Z', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': 'k1'}, ['occurredAt']),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-03-14T10:30:00.123456+05:30', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': 'k1'}, {'ok': {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-03-14T10:30:00.123456+05:30', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'weakParse': False, 'reversal': False, 'dedupeKey': 'k1'}}),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2024-02-29T23:59:59-08:00', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': 'k1'}, {'ok': {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2024-02-29T23:59:59-08:00', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'weakParse': False, 'reversal': False, 'dedupeKey': 'k1'}}),
    ('IngestTransactionReq', {'type': 'debit', 'amountMinor': 500, 'occurredAt': '2025-03-14 10:30:00Z', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'capturedAt': '2025-03-14T10:30:00.000Z', 'dedupeKey': 'k1'}, ['occurredAt']),
    ('IngestTransactionRes', {'outcome': 'created', 'transaction': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}}, 'same'),
    ('IngestTransactionRes', {'outcome': 'duplicate', 'transaction': None}, 'same'),
    ('IngestTransactionRes', {'outcome': 'nope', 'transaction': None}, ['outcome']),
    ('ManualTransactionReq', {'type': 'credit', 'amountMinor': 1, 'occurredAt': '2025-03-14T10:30:00.000Z'}, 'same'),
    ('ManualTransactionReq', {'type': 'credit', 'amountMinor': 1, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': None, 'description': 'ddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd'}, ['description']),
    ('TransactionRes', {'transaction': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}}, 'same'),
    ('RecurringPostReq', {'ruleId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'amountMinor': 100, 'dueDate': '2025-04-01'}, 'same'),
    ('RecurringPostReq', {'ruleId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'amountMinor': 100, 'dueDate': '2025-04-01', 'matchHint': None}, 'same'),
    ('RecurringPostReq', {'ruleId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'amountMinor': 100, 'dueDate': '1-4-2025'}, ['dueDate']),
    ('RecurringPostRes', {'outcome': 'linked', 'transaction': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}}, 'same'),
    ('RecurringPostRes', {'outcome': 'x', 'transaction': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}}, ['outcome']),
    ('TagReq', {'tag': 'food'}, {'ok': {'tag': 'food', 'via': 'web'}}),
    ('TagReq', {'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'via': 'telegram'}, 'same'),
    ('TagReq', {}, ['']),
    ('TagReq', {'tag': 'a', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7'}, ['']),
    ('TagReq', {'tag': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}, ['tag']),
    ('TagReq', {'tag': 'a', 'via': 'sms'}, ['via']),
    ('TagRes', {'transaction': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, 'changed': True, 'previousCategoryId': None, 'alsoTaggedIds': ['3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'], 'categoryCreated': False}, 'same'),
    ('PendingRes', {'count': 1, 'items': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}]}, 'same'),
    ('CategoriesRes', {'items': [{'id': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'name': 'food', 'archived': False}]}, 'same'),
    ('ResolveCategoryReq', {'tag': 'x'}, 'same'),
    ('ResolveCategoryRes', {'category': {'id': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'name': 'food', 'archived': False}, 'created': True}, 'same'),
    ('CategoriesQuery', {}, {'ok': {'sort': 'name', 'includeArchived': False}}),
    ('CategoriesQuery', {'sort': 'usage', 'limit': '6', 'includeArchived': 'true'}, {'ok': {'sort': 'usage', 'limit': 6, 'includeArchived': True}}),
    ('CategoriesQuery', {'includeArchived': 'TRUE'}, {'ok': {'sort': 'name', 'includeArchived': True}}),
    ('CategoriesQuery', {'includeArchived': '0'}, {'ok': {'sort': 'name', 'includeArchived': False}}),
    ('CategoriesQuery', {'includeArchived': 'maybe'}, ['includeArchived']),
    ('CategoriesQuery', {'sort': 'x', 'limit': '0'}, ['limit', 'sort']),
    ('CategoriesQuery', {'includeArchived': 'yes'}, {'ok': {'sort': 'name', 'includeArchived': True}}),
    ('CategoriesQuery', {'includeArchived': 'off'}, {'ok': {'sort': 'name', 'includeArchived': False}}),
    ('SpendByCategoryRes', {'items': [{'categoryId': None, 'categoryName': None, 'spentMinor': 5}]}, 'same'),
    ('SpendQuery', {'from': '2025-03-14T10:30:00.000Z', 'to': '2025-03-14T16:00:00+05:30'}, 'same'),
    ('SpendQuery', {'from': 'x'}, ['from', 'to']),
    ('MonthSummaryRes', {'month': '2025-03', 'carriedOverMinor': 1, 'incomeMinor': 2, 'spentMinor': 3, 'availableMinor': 4, 'untaggedCount': 0, 'unaccountedCount': 0, 'lastCapturedAt': None}, 'same'),
    ('MonthSummaryRes', {'month': '2025-13', 'carriedOverMinor': 1, 'incomeMinor': 2, 'spentMinor': 3, 'availableMinor': 4, 'untaggedCount': 0, 'unaccountedCount': 0, 'lastCapturedAt': None}, ['month']),
    ('MonthSummaryRes', {'month': '2025-03', 'carriedOverMinor': 1, 'incomeMinor': 2, 'spentMinor': 3, 'availableMinor': 4, 'untaggedCount': 0, 'unaccountedCount': 0, 'lastCapturedAt': '2025-03-14T16:00:00+05:30'}, 'same'),
    ('MonthsRes', {'items': [{'month': '2025-01', 'incomeMinor': 1, 'spentMinor': 2, 'closingMinor': -3}]}, 'same'),
    ('CategoryMonthsRes', {'items': [{'month': '2025-01', 'categoryId': None, 'categoryName': None, 'spentMinor': 2}]}, 'same'),
    ('DailyRes', {'items': [{'day': '2025-01-02', 'spentMinor': 2}]}, 'same'),
    ('DailyRes', {'items': [{'day': '2025-1-2', 'spentMinor': 2}]}, ['items.0.day']),
    ('SummaryQuery', {'month': '2025-03'}, 'same'),
    ('SummaryQuery', {'month': '2025-3'}, ['month']),
    ('SummaryQuery', {}, ['month']),
    ('MonthsQuery', {'end': '2025-03'}, {'ok': {'end': '2025-03', 'count': 6}}),
    ('MonthsQuery', {'end': '2025-03', 'count': '24'}, {'ok': {'end': '2025-03', 'count': 24}}),
    ('MonthsQuery', {'end': '2025-03', 'count': '25'}, ['count']),
    ('MonthsQuery', {'end': '2025-03', 'count': ' 3 '}, {'ok': {'end': '2025-03', 'count': 3}}),
    ('DailyQuery', {'month': '2025-03'}, 'same'),
    ('DailyQuery', {'month': '2025-03', 'excludeCategoryIds': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23,7c9e6679-7425-40de-944b-e07fc1f90ae7'}, 'same'),
    ('TransactionSettings', {'openingBalanceMinor': -5, 'reconcileGraceHours': 6}, 'same'),
    ('TransactionSettings', {'openingBalanceMinor': 0, 'reconcileGraceHours': 73}, ['reconcileGraceHours']),
    ('TransactionSettings', {'openingBalanceMinor': 0, 'reconcileGraceHours': -1}, ['reconcileGraceHours']),
    ('TransactionSettingsPatch', {}, 'same'),
    ('TransactionSettingsPatch', {'reconcileGraceHours': 0}, 'same'),
    ('TransactionSettingsPatch', {'reconcileGraceHours': None}, ['reconcileGraceHours']),
    ('TransactionSettingsPatch', {'openingBalanceMinor': 5, 'zzz': 1}, {'ok': {'openingBalanceMinor': 5}}),
    ('TransactionSettingsPatch', {'reconcileGraceHours': 100}, ['reconcileGraceHours']),
    ('TransactionRowDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False, 'classifiedBy': 'rule', 'matchedRule': 'uber'}, 'same'),
    ('TransactionRowDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False, 'classifiedBy': 'x', 'matchedRule': 'uber'}, ['classifiedBy']),
    ('TransactionRowDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, ['classifiedBy', 'matchedRule']),
    ('TransactionsQuery', {}, {'ok': {'src': 'all', 'limit': 8}}),
    ('TransactionsQuery', {'cat': 'food', 'src': 'pending', 'month': '2025-03', 'cursor': 'abc', 'limit': '100'}, {'ok': {'cat': 'food', 'src': 'pending', 'month': '2025-03', 'cursor': 'abc', 'limit': 100}}),
    ('TransactionsQuery', {'src': 'unaccounted'}, {'ok': {'src': 'unaccounted', 'limit': 8}}),
    ('TransactionsQuery', {'src': 'captured'}, {'ok': {'src': 'captured', 'limit': 8}}),
    ('TransactionsQuery', {'src': 'zzz', 'limit': '101'}, ['limit', 'src']),
    ('TransactionsQuery', {'limit': 'abc'}, ['limit']),
    ('TransactionsQuery', {'cat': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}, ['cat']),
    ('CategoryStatDto', {'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'archived': False, 'count': 3, 'spentMinor': 900, 'receivedMinor': 0}, 'same'),
    ('TransactionCountsDto', {'all': 5, 'needsTag': 1, 'unaccounted': 0, 'byCategory': [{'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'archived': False, 'count': 3, 'spentMinor': 900, 'receivedMinor': 0}]}, 'same'),
    ('TransactionPageDto', {'month': '2025-03', 'items': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False, 'classifiedBy': 'rule', 'matchedRule': 'uber'}], 'nextCursor': None, 'matching': 1, 'counts': {'all': 5, 'needsTag': 1, 'unaccounted': 0, 'byCategory': [{'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'archived': False, 'count': 3, 'spentMinor': 900, 'receivedMinor': 0}]}, 'balanceMinor': 37591}, 'same'),
    ('TransactionPageDto', {'month': None, 'items': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False, 'classifiedBy': 'rule', 'matchedRule': 'uber'}], 'nextCursor': 'c', 'matching': 1, 'counts': {'all': 5, 'needsTag': 1, 'unaccounted': 0, 'byCategory': [{'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'archived': False, 'count': 3, 'spentMinor': 900, 'receivedMinor': 0}]}, 'balanceMinor': 37591}, 'same'),
    ('TransactionPageDto', {'month': '2025-03', 'items': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}], 'nextCursor': None, 'matching': 1, 'counts': {'all': 5, 'needsTag': 1, 'unaccounted': 0, 'byCategory': [{'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'archived': False, 'count': 3, 'spentMinor': 900, 'receivedMinor': 0}]}, 'balanceMinor': 37591}, ['items.0.classifiedBy', 'items.0.matchedRule']),
    ('TransactionFigures', {'balanceMinor': 1000, 'needsTagCount': 1, 'unaccountedCount': 0, 'categories': [{'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'archived': False, 'count': 3, 'spentMinor': 900, 'receivedMinor': 0}]}, 'same'),
    ('PatchTransactionReq', {'tag': 'x'}, {'ok': {'tag': 'x', 'recategorize': False}}),
    ('PatchTransactionReq', {'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'recategorize': True}, 'same'),
    ('PatchTransactionReq', {}, ['']),
    ('PatchTransactionReq', {'tag': 'x', 'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'}, ['']),
    ('PatchTransactionRes', {'transaction': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, 'changed': False, 'previousCategoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'alsoTaggedIds': [], 'categoryCreated': False, 'figures': {'balanceMinor': 1000, 'needsTagCount': 1, 'unaccountedCount': 0, 'categories': [{'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'archived': False, 'count': 3, 'spentMinor': 900, 'receivedMinor': 0}]}}, 'same'),
    ('PatchTransactionRes', {'transaction': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, 'changed': False, 'previousCategoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'alsoTaggedIds': [], 'categoryCreated': False}, ['figures']),
    ('SplitReq', {'parts': [{'amountMinor': 1, 'tag': 'a'}, {'amountMinor': 2}]}, 'same'),
    ('SplitReq', {'parts': [{'amountMinor': 1}]}, ['parts']),
    ('SplitReq', {'parts': [{'amountMinor': 1, 'tag': 'a', 'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'}, {'amountMinor': 0}]}, ['parts.0', 'parts.1.amountMinor']),
    ('SplitReq', {'parts': [{'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}, {'amountMinor': 1}]}, ['parts']),
    ('SplitRes', {'items': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}], 'figures': {'balanceMinor': 1000, 'needsTagCount': 1, 'unaccountedCount': 0, 'categories': [{'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'archived': False, 'count': 3, 'spentMinor': 900, 'receivedMinor': 0}]}}, 'same'),
    ('CreditReq', {'amountMinor': 100, 'date': '2025-03-14', 'tag': 'salary'}, {'ok': {'amountMinor': 100, 'date': '2025-03-14', 'tag': 'salary', 'addToPlan': True}}),
    ('CreditReq', {'amountMinor': 100, 'date': '2025-03-14', 'tag': 'salary', 'note': None, 'addToPlan': False}, 'same'),
    ('CreditReq', {'amountMinor': 100, 'date': '14/03/2025', 'tag': ''}, ['date', 'tag']),
    ('CreditReq', {'amountMinor': 100, 'date': '2025-03-14', 'tag': 's', 'note': 'nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn'}, ['note']),
    ('CreditRes', {'transaction': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, 'categoryCreated': True, 'balanceMinor': 5, 'planTotalMinor': None}, 'same'),
    ('CreditsQuery', {}, {'ok': {'limit': 5}}),
    ('CreditsQuery', {'limit': '50'}, {'ok': {'limit': 50}}),
    ('CreditsQuery', {'limit': '51'}, ['limit']),
    ('CreditsRes', {'items': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}], 'balanceMinor': 1}, 'same'),
    ('CategoryUsageDto', {'id': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'name': 'food', 'archived': False, 'count': 3}, 'same'),
    ('CategoriesUsageRes', {'items': [{'id': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'name': 'food', 'archived': False, 'count': 3}]}, 'same'),
    ('CreateCategoryReq', {'name': 'x'}, 'same'),
    ('CreateCategoryReq', {'name': ''}, ['name']),
    ('PatchCategoryReq', {'name': 'x'}, 'same'),
    ('PatchCategoryReq', {'archived': False}, 'same'),
    ('PatchCategoryReq', {}, ['']),
    ('DeleteCategoryQuery', {}, 'same'),
    ('DeleteCategoryQuery', {'reassignTo': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'}, 'same'),
    ('DeleteCategoryQuery', {'reassignTo': 'x'}, ['reassignTo']),
    ('DeleteCategoryRes', {'ok': True, 'reassigned': 3}, 'same'),
    ('BalanceCheckDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'bankBalanceMinor': 5000, 'transactionsBalanceMinor': 5100, 'gapMinor': -100, 'source': 'message', 'status': 'open', 'checkedAt': '2025-03-14T10:30:00.000Z', 'asOf': '2025-03-14T16:00:00+05:30', 'transactionId': None, 'graceEndsAt': '2025-03-14T10:30:00Z'}, 'same'),
    ('BalanceCheckDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'bankBalanceMinor': 5000, 'transactionsBalanceMinor': 5100, 'gapMinor': -100, 'source': 'y', 'status': 'x', 'checkedAt': '2025-03-14T10:30:00.000Z', 'asOf': '2025-03-14T16:00:00+05:30', 'transactionId': None, 'graceEndsAt': '2025-03-14T10:30:00Z'}, ['source', 'status']),
    ('BalanceCheckReq', {'bankBalanceMinor': -100}, 'same'),
    ('BalanceCheckReq', {'bankBalanceMinor': 1.5}, ['bankBalanceMinor']),
    ('BalanceCheckRes', {'check': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'bankBalanceMinor': 5000, 'transactionsBalanceMinor': 5100, 'gapMinor': -100, 'source': 'message', 'status': 'open', 'checkedAt': '2025-03-14T10:30:00.000Z', 'asOf': '2025-03-14T16:00:00+05:30', 'transactionId': None, 'graceEndsAt': '2025-03-14T10:30:00Z'}, 'matches': False, 'transactionsBalanceMinor': 5100, 'transaction': None}, 'same'),
    ('BalanceChecksQuery', {}, {'ok': {'limit': 10}}),
    ('BalanceChecksQuery', {'limit': '50'}, {'ok': {'limit': 50}}),
    ('BalanceChecksQuery', {'limit': '51'}, ['limit']),
    ('BalanceChecksRes', {'items': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'bankBalanceMinor': 5000, 'transactionsBalanceMinor': 5100, 'gapMinor': -100, 'source': 'message', 'status': 'open', 'checkedAt': '2025-03-14T10:30:00.000Z', 'asOf': '2025-03-14T16:00:00+05:30', 'transactionId': None, 'graceEndsAt': '2025-03-14T10:30:00Z'}]}, 'same'),
    ('IngestBody', {'text': 'Rs 5 debited', 'receivedAt': '2025-03-14T16:00:00+05:30', 'nonce': '12345678'}, 'same'),
    ('IngestBody', {'text': 't', 'receivedAt': '2025-03-14T10:30:00.000Z', 'nonce': '12345678', 'sender': 'AX-HDFCBK'}, 'same'),
    ('IngestBody', {'text': '', 'receivedAt': '2025-01-01T10:00:00', 'nonce': '1'}, ['nonce', 'receivedAt']),
    ('IngestBody', {'text': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'receivedAt': '2025-03-14T10:30:00.000Z', 'nonce': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'sender': ''}, ['nonce', 'sender', 'text']),
    ('IngestMessageRes', {'outcome': 'created', 'transaction': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 5, 'status': 'pending'}}, 'same'),
    ('IngestMessageRes', {'outcome': 'ignored', 'transaction': None, 'reason': 'otp_or_promo'}, 'same'),
    ('IngestMessageRes', {'outcome': 'test', 'transaction': None}, 'same'),
    ('IngestMessageRes', {'outcome': 'weird', 'transaction': None, 'reason': 'zzz'}, ['outcome', 'reason']),
    ('DeviceDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'iPhone', 'lastSeenAt': None, 'revokedAt': None, 'createdAt': '2025-03-14T10:30:00.000Z', 'tokenHint': 'ledg_live_8f3a…b605', 'rotatedAt': None, 'lastDelaySeconds': None, 'allowedSenders': ['AX-HDFCBK'], 'lastTest': {'at': '2025-03-14T10:30:00.000Z', 'source': 'web', 'delaySeconds': 3, 'amountMinor': 100}}, 'same'),
    ('DeviceDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'iPhone', 'lastSeenAt': None, 'revokedAt': None, 'createdAt': '2025-03-14T10:30:00.000Z', 'tokenHint': 'ledg_live_8f3a…b605', 'rotatedAt': None, 'lastDelaySeconds': None, 'allowedSenders': ['AX-HDFCBK'], 'lastTest': None}, 'same'),
    ('DeviceDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'iPhone', 'lastSeenAt': None, 'revokedAt': None, 'createdAt': '2025-03-14T10:30:00.000Z', 'tokenHint': 'ledg_live_8f3a…b605', 'rotatedAt': None, 'lastDelaySeconds': None, 'allowedSenders': ['AX-HDFCBK'], 'lastTest': {'at': '2025-03-14T10:30:00.000Z', 'source': 'sms', 'delaySeconds': None, 'amountMinor': None}}, ['lastTest.source']),
    ('DevicesRes', {'devices': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'iPhone', 'lastSeenAt': None, 'revokedAt': None, 'createdAt': '2025-03-14T10:30:00.000Z', 'tokenHint': 'ledg_live_8f3a…b605', 'rotatedAt': None, 'lastDelaySeconds': None, 'allowedSenders': ['AX-HDFCBK'], 'lastTest': {'at': '2025-03-14T10:30:00.000Z', 'source': 'web', 'delaySeconds': 3, 'amountMinor': 100}}]}, 'same'),
    ('CreateDeviceReq', {}, 'same'),
    ('CreateDeviceReq', {'name': ' Phone ', 'code': '123456', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'allowedSenders': [' AX-HDFCBK ']}, {'ok': {'name': 'Phone', 'code': '123456', 'deviceId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'allowedSenders': ['AX-HDFCBK']}}),
    ('CreateDeviceReq', {'code': '12345'}, ['code']),
    ('CreateDeviceReq', {'allowedSenders': ['a']}, ['allowedSenders.0']),
    ('CreateDeviceReq', {'allowedSenders': ['ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab', 'ab']}, ['allowedSenders']),
    ('CreateDeviceReq', {'name': '  '}, ['name']),
    ('CreateDeviceReq', {'name': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}, ['name']),
    ('DeviceTokenRes', {'device': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'iPhone', 'lastSeenAt': None, 'revokedAt': None, 'createdAt': '2025-03-14T10:30:00.000Z', 'tokenHint': 'ledg_live_8f3a…b605', 'rotatedAt': None, 'lastDelaySeconds': None, 'allowedSenders': ['AX-HDFCBK'], 'lastTest': {'at': '2025-03-14T10:30:00.000Z', 'source': 'web', 'delaySeconds': 3, 'amountMinor': 100}}, 'token': 'tok', 'rotated': False}, 'same'),
    ('RevokeDeviceReq', {}, 'same'),
    ('RevokeDeviceReq', {'code': '123456'}, 'same'),
    ('RevokeDeviceReq', {'code': '1'}, ['code']),
    ('RevokeDeviceRes', {'device': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'iPhone', 'lastSeenAt': None, 'revokedAt': None, 'createdAt': '2025-03-14T10:30:00.000Z', 'tokenHint': 'ledg_live_8f3a…b605', 'rotatedAt': None, 'lastDelaySeconds': None, 'allowedSenders': ['AX-HDFCBK'], 'lastTest': {'at': '2025-03-14T10:30:00.000Z', 'source': 'web', 'delaySeconds': 3, 'amountMinor': 100}}}, 'same'),
    ('PatchDeviceReq', {}, 'same'),
    ('PatchDeviceReq', {'name': ' N ', 'allowedSenders': ['AB']}, {'ok': {'name': 'N', 'allowedSenders': ['AB']}}),
    ('TestDeviceRes', {'ok': True, 'device': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'iPhone', 'lastSeenAt': None, 'revokedAt': None, 'createdAt': '2025-03-14T10:30:00.000Z', 'tokenHint': 'ledg_live_8f3a…b605', 'rotatedAt': None, 'lastDelaySeconds': None, 'allowedSenders': ['AX-HDFCBK'], 'lastTest': {'at': '2025-03-14T10:30:00.000Z', 'source': 'web', 'delaySeconds': 3, 'amountMinor': 100}}, 'amountMinor': 100, 'type': 'debit'}, 'same'),
    ('UnparsedDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'receivedAt': '2025-03-14T10:30:00.000Z', 'expiresAt': '2025-03-14T16:00:00+05:30', 'reason': 'no_amount', 'text': 'msg', 'suggestion': {'type': None, 'amountMinor': None, 'payee': None}}, 'same'),
    ('UnparsedDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'receivedAt': '2025-03-14T10:30:00.000Z', 'expiresAt': '2025-03-14T16:00:00+05:30', 'reason': 'no_amount', 'text': 'msg', 'suggestion': {'type': 'credit', 'amountMinor': 5, 'payee': 'x'}}, 'same'),
    ('UnparsedDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'receivedAt': '2025-03-14T10:30:00.000Z', 'expiresAt': '2025-03-14T16:00:00+05:30', 'reason': 'x', 'text': 'msg', 'suggestion': {'type': None, 'amountMinor': None, 'payee': None}}, ['reason']),
    ('UnparsedRes', {'items': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'receivedAt': '2025-03-14T10:30:00.000Z', 'expiresAt': '2025-03-14T16:00:00+05:30', 'reason': 'no_amount', 'text': 'msg', 'suggestion': {'type': None, 'amountMinor': None, 'payee': None}}], 'open': 1}, 'same'),
    ('ResolveUnparsedReq', {'type': 'debit', 'amountMinor': 5}, 'same'),
    ('ResolveUnparsedReq', {'type': 'debit', 'amountMinor': 5, 'payee': '  Shop '}, {'ok': {'type': 'debit', 'amountMinor': 5, 'payee': 'Shop'}}),
    ('ResolveUnparsedReq', {'type': 'debit', 'amountMinor': 5, 'payee': None}, 'same'),
    ('ResolveUnparsedReq', {'type': 'x', 'amountMinor': 0}, ['amountMinor', 'type']),
    ('ResolveUnparsedRes', {'transaction': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'type': 'debit', 'amountMinor': 45000, 'occurredAt': '2025-03-14T10:30:00.000Z', 'payee': 'Swiggy', 'description': None, 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None, 'capturedAt': '2025-03-14T16:00:00+05:30', 'weakParse': False}, 'open': 0}, 'same'),
    ('DismissUnparsedRes', {'ok': True, 'open': 2}, 'same'),
    ('UnparsedCountRes', {'open': 2}, 'same'),
    ('PlanDto', {'month': '2025-03', 'totalMinor': 100, 'lines': [{'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'categoryName': 'food', 'allocatedMinor': 50}]}, 'same'),
    ('PlanWithSpendDto', {'month': '2025-03', 'totalMinor': 100, 'lines': [{'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'categoryName': 'food', 'allocatedMinor': 50, 'spentMinor': 20}], 'assignedMinor': 50, 'unassignedMinor': 50}, 'same'),
    ('PlanWithSpendDto', {'month': '2025-03', 'totalMinor': 100, 'lines': [{'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'categoryName': 'food', 'allocatedMinor': 50}], 'assignedMinor': 50, 'unassignedMinor': 50}, ['lines.0.spentMinor']),
    ('BudgetDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'limitMinor': 1000, 'period': 'monthly', 'warnPct': None, 'active': True, 'spentMinor': 10, 'pct': 1, 'projectedMinor': 30, 'status': 'ok'}, 'same'),
    ('BudgetDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'limitMinor': 1000, 'period': 'monthly', 'warnPct': 80, 'active': True, 'spentMinor': 10, 'pct': 1, 'projectedMinor': 30, 'status': 'ok'}, 'same'),
    ('BudgetDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'limitMinor': 1000, 'period': 'monthly', 'warnPct': 49, 'active': True, 'spentMinor': 10, 'pct': 1, 'projectedMinor': 30, 'status': 'ok'}, ['warnPct']),
    ('BudgetDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'limitMinor': 1000, 'period': 'weekly', 'warnPct': 100, 'active': True, 'spentMinor': 10, 'pct': 1, 'projectedMinor': 30, 'status': 'x'}, ['period', 'status', 'warnPct']),
    ('BudgetsRes', {'month': '2025-03', 'alertLevel': 80, 'items': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'limitMinor': 1000, 'period': 'monthly', 'warnPct': None, 'active': True, 'spentMinor': 10, 'pct': 1, 'projectedMinor': 30, 'status': 'ok'}]}, 'same'),
    ('AlertDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'budgetId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'level': 'alert', 'periodKey': '2025-03', 'sentAt': '2025-03-01T00:00:00Z', 'readAt': None}, 'same'),
    ('AlertDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'budgetId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'level': 'x', 'periodKey': '2025-03', 'sentAt': '2025-03-01T00:00:00Z', 'readAt': None}, ['level']),
    ('AlertsRes', {'unreadCount': 1, 'items': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'budgetId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'level': 'alert', 'periodKey': '2025-03', 'sentAt': '2025-03-01T00:00:00Z', 'readAt': None}]}, 'same'),
    ('AlertReadRes', {'alert': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'budgetId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'food', 'level': 'alert', 'periodKey': '2025-03', 'sentAt': '2025-03-01T00:00:00Z', 'readAt': None}, 'unreadCount': 0}, 'same'),
    ('PlanningSettings', {'alertLevel': 80, 'warnOnPace': True}, 'same'),
    ('PlanningSettings', {'alertLevel': 75, 'warnOnPace': 'yes'}, ['alertLevel', 'warnOnPace']),
    ('PlanningSettings', {'alertLevel': '80', 'warnOnPace': True}, ['alertLevel']),
    ('PlanningSettingsPatch', {}, 'same'),
    ('PlanningSettingsPatch', {'alertLevel': 70}, 'same'),
    ('PlanningSettingsPatch', {'alertLevel': 71}, ['alertLevel']),
    ('PlanningSettingsPatch', {'warnOnPace': None}, ['warnOnPace']),
    ('PlanCreditReq', {'transactionId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'amountMinor': 5}, 'same'),
    ('PlanCreditReq', {'transactionId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'amountMinor': 0}, ['amountMinor']),
    ('PlanCreditRes', {'totalMinor': 5}, 'same'),
    ('PlanLineInput', {'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'allocatedMinor': 0}, 'same'),
    ('PlanLineInput', {'tag': 'food', 'allocatedMinor': 5}, 'same'),
    ('PlanLineInput', {'allocatedMinor': 5}, ['categoryId']),
    ('PlanLineInput', {'tag': 'x', 'allocatedMinor': 1.5}, ['allocatedMinor']),
    ('PlanPutReq', {'totalMinor': 100, 'lines': [{'tag': 'food', 'allocatedMinor': 5}, {'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'allocatedMinor': 0}]}, 'same'),
    ('PlanPutReq', {'totalMinor': -1, 'lines': [{'allocatedMinor': 1}]}, ['lines.0.categoryId', 'totalMinor']),
    ('PlanPutReq', {'totalMinor': 0, 'lines': [{'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}, {'tag': 'x', 'allocatedMinor': 1}]}, ['lines']),
    ('PlanPutReq', {'totalMinor': 0}, ['lines']),
    ('BudgetsQuery', {}, 'same'),
    ('BudgetsQuery', {'month': '2025-03'}, 'same'),
    ('BudgetCreateReq', {'tag': 'food', 'limitMinor': 1000}, {'ok': {'tag': 'food', 'limitMinor': 1000, 'period': 'monthly', 'useMonthAllocation': False}}),
    ('BudgetCreateReq', {'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'useMonthAllocation': True, 'month': '2025-03', 'warnPct': None}, {'ok': {'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'period': 'monthly', 'warnPct': None, 'useMonthAllocation': True, 'month': '2025-03'}}),
    ('BudgetCreateReq', {'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'}, ['limitMinor']),
    ('BudgetCreateReq', {}, ['categoryId', 'limitMinor']),
    ('BudgetCreateReq', {'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'tag': 'x', 'limitMinor': 1, 'warnPct': 30, 'period': 'weekly'}, ['period', 'warnPct']),
    ('BudgetCreateReq', {'tag': 'x', 'limitMinor': 1, 'warnPct': 90}, {'ok': {'tag': 'x', 'limitMinor': 1, 'period': 'monthly', 'warnPct': 90, 'useMonthAllocation': False}}),
    ('BudgetPatchReq', {'limitMinor': 5}, 'same'),
    ('BudgetPatchReq', {'warnPct': None}, 'same'),
    ('BudgetPatchReq', {}, ['']),
    ('BudgetPatchReq', {'active': False}, 'same'),
    ('BudgetPatchReq', {'useMonthAllocation': True, 'month': '2025-03'}, 'same'),
    ('Schedule', {'kind': 'monthly', 'day': 31}, 'same'),
    ('Schedule', {'kind': 'weekly', 'weekday': 0}, 'same'),
    ('Schedule', {'kind': 'yearly', 'month': 12, 'day': 25}, 'same'),
    ('Schedule', {'kind': 'monthly', 'day': 32}, ['day']),
    ('Schedule', {'kind': 'weekly', 'weekday': 7}, ['weekday']),
    ('Schedule', {'kind': 'yearly', 'month': 13, 'day': 0}, ['day', 'month']),
    ('Schedule', {'kind': 'daily'}, ['kind']),
    ('Schedule', {}, ['kind']),
    ('Schedule', None, ['']),
    ('Schedule', {'kind': 'monthly'}, ['day']),
    ('Schedule', {'kind': 'monthly', 'day': 5, 'extra': 1}, {'ok': {'kind': 'monthly', 'day': 5}}),
    ('RecurringRuleDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'rent', 'amountMinor': 1500000, 'schedule': {'kind': 'monthly', 'day': 1}, 'nextDue': '2025-04-01', 'paused': False, 'endsOn': None}, {'ok': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'rent', 'amountMinor': 1500000, 'schedule': {'kind': 'monthly', 'day': 1}, 'nextDue': '2025-04-01', 'paused': False, 'endsOn': None, 'note': None, 'matchHint': None, 'active': True}}),
    ('RecurringRuleDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'rent', 'amountMinor': 1500000, 'schedule': {'kind': 'monthly', 'day': 1}, 'nextDue': '2025-04-01', 'paused': False, 'endsOn': '2026-01-01', 'note': 'n', 'matchHint': 'uber', 'active': False}, 'same'),
    ('RecurringRuleDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'rent', 'amountMinor': 1500000, 'schedule': {'kind': 'x'}, 'nextDue': '2025-04-01', 'paused': False, 'endsOn': None}, ['schedule.kind']),
    ('RecurringRuleDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'rent', 'amountMinor': 1500000, 'schedule': {'kind': 'monthly', 'day': 1}, 'nextDue': '2025-04-01', 'paused': False, 'endsOn': None, 'note': None, 'matchHint': None}, {'ok': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'rent', 'amountMinor': 1500000, 'schedule': {'kind': 'monthly', 'day': 1}, 'nextDue': '2025-04-01', 'paused': False, 'endsOn': None, 'note': None, 'matchHint': None, 'active': True}}),
    ('RecurringRuleDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'rent', 'amountMinor': 1500000, 'schedule': {'kind': 'monthly', 'day': 1}, 'nextDue': 'soon', 'paused': False, 'endsOn': None}, ['nextDue']),
    ('RecurringRes', {'items': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'rent', 'amountMinor': 1500000, 'schedule': {'kind': 'monthly', 'day': 1}, 'nextDue': '2025-04-01', 'paused': False, 'endsOn': None}], 'committedMinor': 1500000}, {'ok': {'items': [{'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'rent', 'amountMinor': 1500000, 'schedule': {'kind': 'monthly', 'day': 1}, 'nextDue': '2025-04-01', 'paused': False, 'endsOn': None, 'note': None, 'matchHint': None, 'active': True}], 'committedMinor': 1500000}}),
    ('CreateRecurringReq', {'name': ' Rent ', 'tag': 'rent', 'amountMinor': 100, 'schedule': {'kind': 'monthly', 'day': 1}}, {'ok': {'name': 'Rent', 'tag': 'rent', 'amountMinor': 100, 'schedule': {'kind': 'monthly', 'day': 1}}}),
    ('CreateRecurringReq', {'name': ' Rent ', 'amountMinor': 100, 'schedule': {'kind': 'monthly', 'day': 1}, 'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'startsOn': '2025-04-01', 'endsOn': None, 'matchHint': '  uber  ', 'note': '  to landlord '}, {'ok': {'name': 'Rent', 'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'amountMinor': 100, 'schedule': {'kind': 'monthly', 'day': 1}, 'startsOn': '2025-04-01', 'endsOn': None, 'matchHint': 'uber', 'note': 'to landlord'}}),
    ('CreateRecurringReq', {'name': ' Rent ', 'amountMinor': 100, 'schedule': {'kind': 'monthly', 'day': 1}}, ['']),
    ('CreateRecurringReq', {'name': ' Rent ', 'tag': 'rent', 'amountMinor': 100, 'schedule': {'kind': 'monthly', 'day': 1}, 'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'}, ['']),
    ('CreateRecurringReq', {'name': '  ', 'tag': 'rent', 'amountMinor': 100, 'schedule': {'kind': 'monthly', 'day': 1}}, ['name']),
    ('CreateRecurringReq', {'name': ' Rent ', 'tag': 'rent', 'amountMinor': 100, 'schedule': {'kind': 'monthly', 'day': 1}, 'matchHint': '  '}, ['matchHint']),
    ('CreateRecurringReq', {'name': ' Rent ', 'tag': 'rent', 'amountMinor': 100, 'schedule': {'kind': 'monthly', 'day': 1}, 'note': 'nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn'}, ['note']),
    ('CreateRecurringReq', {'name': ' Rent ', 'tag': 'rent', 'amountMinor': 100, 'schedule': {'kind': 'monthly', 'day': 0}}, ['schedule.day']),
    ('CreateRecurringReq', {'name': ' Rent ', 'tag': 'rent', 'amountMinor': 100, 'schedule': {'kind': 'monthly', 'day': 1}, 'startsOn': 'tomorrow'}, ['startsOn']),
    ('PatchRecurringReq', {'paused': True}, 'same'),
    ('PatchRecurringReq', {'skipNext': True}, 'same'),
    ('PatchRecurringReq', {'skipNext': False}, ['skipNext']),
    ('PatchRecurringReq', {}, ['']),
    ('PatchRecurringReq', {'tag': 'a', 'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'}, ['']),
    ('PatchRecurringReq', {'endsOn': None}, 'same'),
    ('PatchRecurringReq', {'note': None, 'matchHint': None, 'name': ' X '}, {'ok': {'name': 'X', 'matchHint': None, 'note': None}}),
    ('PatchRecurringReq', {'schedule': {'kind': 'weekly', 'weekday': 3}, 'amountMinor': 5}, 'same'),
    ('PatchRecurringReq', {'schedule': {'kind': 'weekly', 'weekday': 9}}, ['schedule.weekday']),
    ('RecurringMutationRes', {'rule': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'rent', 'amountMinor': 1500000, 'schedule': {'kind': 'monthly', 'day': 1}, 'nextDue': '2025-04-01', 'paused': False, 'endsOn': None}, 'committedMinor': 5}, {'ok': {'rule': {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'Rent', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'categoryName': 'rent', 'amountMinor': 1500000, 'schedule': {'kind': 'monthly', 'day': 1}, 'nextDue': '2025-04-01', 'paused': False, 'endsOn': None, 'note': None, 'matchHint': None, 'active': True}, 'committedMinor': 5}}),
    ('RecurringDeleteRes', {'ok': True, 'committedMinor': 0}, 'same'),
    ('DashboardQuery', {}, 'same'),
    ('DashboardQuery', {'month': '2025-03'}, 'same'),
    ('ReportDailyQuery', {'month': 'x'}, ['month']),
    ('ReportRangeQuery', {}, {'ok': {'range': 6}}),
    ('ReportRangeQuery', {'range': '12'}, {'ok': {'range': 12}}),
    ('ReportRangeQuery', {'range': '0'}, ['range']),
    ('ReportRangeQuery', {'range': '25'}, ['range']),
    ('AttentionItem', {'kind': 'limit', 'category': 'Fun', 'pct': 85, 'status': 'close'}, 'same'),
    ('AttentionItem', {'kind': 'limit', 'category': 'Fun', 'pct': 85, 'status': 'ok'}, ['status']),
    ('AttentionItem', {'kind': 'untagged', 'count': 3}, 'same'),
    ('AttentionItem', {'kind': 'needs_look', 'count': 1}, 'same'),
    ('AttentionItem', {'kind': 'unaccounted', 'count': 1}, 'same'),
    ('AttentionItem', {'kind': 'recurring', 'name': 'Rent', 'amount': 100, 'due': '2025-04-01'}, 'same'),
    ('AttentionItem', {'kind': 'x'}, ['kind']),
    ('AttentionItem', {'kind': 'recurring', 'name': 'Rent'}, ['amount', 'due']),
    ('DashboardRes', {'month': '2025-03', 'dayOfMonth': 14, 'daysInMonth': 31, 'balance': {'carriedOver': 1, 'income': 2, 'spent': 3, 'available': 4}, 'safeToSpend': {'planLeft': 5, 'daysLeft': 18, 'perDay': 6}, 'flow': [{'name': 'food', 'amount': 5}, {'name': 'Still available', 'amount': 1}], 'attention': [{'kind': 'untagged', 'count': 2}, {'kind': 'recurring', 'name': 'Rent', 'amount': 100, 'due': '2025-04-01'}], 'lastCapturedAt': '2025-03-14T16:00:00+05:30', 'untaggedCount': 2, 'unaccountedCount': 0, 'needsLookCount': 1, 'alertBadgeCount': 0, 'degraded': ['ingest']}, 'same'),
    ('DashboardRes', {'month': '2025-03', 'dayOfMonth': 14, 'daysInMonth': 31, 'balance': {'carriedOver': 1, 'income': 2, 'spent': 3, 'available': 4}, 'safeToSpend': {'planLeft': 5, 'daysLeft': 18, 'perDay': 6}, 'flow': [{'name': 'food', 'amount': 5}, {'name': 'Still available', 'amount': 1}], 'attention': [], 'lastCapturedAt': None, 'untaggedCount': 2, 'unaccountedCount': 0, 'needsLookCount': 1, 'alertBadgeCount': 0, 'degraded': ['ingest']}, 'same'),
    ('DashboardRes', {'month': '2025-03', 'dayOfMonth': 14, 'daysInMonth': 31, 'balance': {'carriedOver': 1, 'income': 2, 'spent': 3, 'available': 4}, 'safeToSpend': {'planLeft': 5, 'daysLeft': 18, 'perDay': 6}, 'flow': [{'name': 'food', 'amount': 5}, {'name': 'Still available', 'amount': 1}], 'attention': [{'kind': 'bogus'}], 'lastCapturedAt': '2025-03-14T16:00:00+05:30', 'untaggedCount': 2, 'unaccountedCount': 0, 'needsLookCount': 1, 'alertBadgeCount': 0, 'degraded': ['ingest']}, ['attention.0.kind']),
    ('DashboardRes', {'month': '2025-03', 'dayOfMonth': 14, 'daysInMonth': 31, 'balance': {'carriedOver': 1, 'income': 2, 'spent': 3, 'available': 4}, 'safeToSpend': {'planLeft': 5, 'daysLeft': 18, 'perDay': 6}, 'flow': [{'name': 'food', 'amount': 5}, {'name': 'Still available', 'amount': 1}], 'attention': [{'kind': 'untagged', 'count': 2}, {'kind': 'recurring', 'name': 'Rent', 'amount': 100, 'due': '2025-04-01'}], 'lastCapturedAt': '2025-03-14T16:00:00+05:30', 'untaggedCount': 2, 'unaccountedCount': 0, 'needsLookCount': 1, 'alertBadgeCount': 0}, ['degraded']),
    ('ReportDailyRes', {'month': '2025-03', 'dayOfMonth': 14, 'daysInMonth': 31, 'items': [{'day': '2025-03-01', 'spentMinor': 5}], 'totalMinor': 5, 'averageMinor': 1, 'fixedCategories': ['Rent']}, 'same'),
    ('MonthPace', {'dayOfMonth': 10, 'daysInMonth': 31, 'spentSoFarMinor': 1, 'flexibleSoFarMinor': 2, 'fixedMinor': 3, 'flexiblePaceMinor': 4, 'paceSpentMinor': 5, 'paceKeptMinor': 6}, 'same'),
    ('MonthPace', {'dayOfMonth': 1.5, 'daysInMonth': 31, 'spentSoFarMinor': 1, 'flexibleSoFarMinor': 2, 'fixedMinor': 3, 'flexiblePaceMinor': 4, 'paceSpentMinor': 5, 'paceKeptMinor': 6}, ['dayOfMonth']),
    ('ReportMonthItem', {'month': '2025-03', 'incomeMinor': 10, 'spentMinor': 5, 'keptMinor': 5, 'keptRate': 0.5, 'closingMinor': 100, 'inProgress': True, 'pace': {'dayOfMonth': 10, 'daysInMonth': 31, 'spentSoFarMinor': 1, 'flexibleSoFarMinor': 2, 'fixedMinor': 3, 'flexiblePaceMinor': 4, 'paceSpentMinor': 5, 'paceKeptMinor': 6}}, 'same'),
    ('ReportMonthItem', {'month': '2025-03', 'incomeMinor': 10, 'spentMinor': 5, 'keptMinor': 5, 'keptRate': 0, 'closingMinor': 100, 'inProgress': True, 'pace': None}, 'same'),
    ('ReportMonthItem', {'month': '2025-03', 'incomeMinor': 10, 'spentMinor': 5, 'keptMinor': 5, 'keptRate': '0.5', 'closingMinor': 100, 'inProgress': True, 'pace': {'dayOfMonth': 10, 'daysInMonth': 31, 'spentSoFarMinor': 1, 'flexibleSoFarMinor': 2, 'fixedMinor': 3, 'flexiblePaceMinor': 4, 'paceSpentMinor': 5, 'paceKeptMinor': 6}}, ['keptRate']),
    ('ReportMonthsRes', {'end': '2025-03', 'items': [{'month': '2025-03', 'incomeMinor': 10, 'spentMinor': 5, 'keptMinor': 5, 'keptRate': 0.5, 'closingMinor': 100, 'inProgress': True, 'pace': {'dayOfMonth': 10, 'daysInMonth': 31, 'spentSoFarMinor': 1, 'flexibleSoFarMinor': 2, 'fixedMinor': 3, 'flexiblePaceMinor': 4, 'paceSpentMinor': 5, 'paceKeptMinor': 6}}], 'averages': {'fullMonths': 2, 'avgMonthlySpendMinor': 1, 'avgKeptMinor': 2, 'avgKeptRate': 0.118, 'balanceSinceMinor': 3, 'balanceSinceMonth': None}}, 'same'),
    ('ReportMonthsRes', {'end': '2025-03', 'items': [], 'averages': {'fullMonths': 2, 'avgMonthlySpendMinor': 1, 'avgKeptMinor': 2, 'avgKeptRate': 0.118, 'balanceSinceMinor': 3, 'balanceSinceMonth': '2025-01'}}, 'same'),
    ('ReportMatrixItem', {'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'food', 'byMonth': [{'month': '2025-02', 'spentMinor': 5}], 'usualMinor': 5, 'spentSoFarMinor': 2, 'paceMinor': 6, 'changeMinor': 1}, 'same'),
    ('ReportMatrixRes', {'end': '2025-03', 'months': ['2025-02', '2025-03'], 'fullMonths': 1, 'dayOfMonth': 14, 'daysInMonth': 31, 'items': [{'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'name': 'food', 'byMonth': [{'month': '2025-02', 'spentMinor': 5}], 'usualMinor': 5, 'spentSoFarMinor': 2, 'paceMinor': 6, 'changeMinor': 1}]}, 'same'),
    ('ReportMatrixRes', {'end': '2025-03', 'months': ['2025-2'], 'fullMonths': 1, 'dayOfMonth': 14, 'daysInMonth': 31, 'items': []}, ['months.0']),
    ('TelegramSettings', {'allowReveal': True, 'sessionIdleDays': 30, 'digestMode': 'daily', 'digestHour': 21, 'afterTag': 'line'}, 'same'),
    ('TelegramSettings', {'allowReveal': True, 'sessionIdleDays': 0, 'digestMode': 'x', 'digestHour': 24, 'afterTag': 'y'}, ['afterTag', 'digestHour', 'digestMode', 'sessionIdleDays']),
    ('TelegramSettings', {'allowReveal': True, 'sessionIdleDays': 91, 'digestMode': 'daily', 'digestHour': -1, 'afterTag': 'line'}, ['digestHour', 'sessionIdleDays']),
    ('TelegramSettingsPatch', {}, 'same'),
    ('TelegramSettingsPatch', {'digestHour': 0, 'afterTag': 'keep'}, 'same'),
    ('TelegramSettingsPatch', {'digestMode': None}, ['digestMode']),
    ('TelegramLinkStatus', {'botSaved': True, 'botUsername': 'my_bot', 'ownerTelegram': '@me', 'linked': True, 'telegramIdHint': '••4821', 'telegramUsername': None, 'linkedAt': '2025-03-14T10:30:00.000Z', 'sessionActive': True, 'sessionSince': '2025-03-14T16:00:00+05:30', 'lastSeenAt': None, 'signInPausedUntil': None, 'pairingPending': False, 'heldCount': 0}, 'same'),
    ('TelegramLinkStatus', {'botSaved': True, 'botUsername': None, 'ownerTelegram': None, 'linked': True, 'telegramIdHint': None, 'telegramUsername': None, 'linkedAt': None, 'sessionActive': True, 'sessionSince': None, 'lastSeenAt': None, 'signInPausedUntil': None, 'pairingPending': False, 'heldCount': 0}, 'same'),
    ('TelegramLinkStatus', {'botSaved': True, 'botUsername': 'my_bot', 'ownerTelegram': '@me', 'linked': True, 'telegramIdHint': '••4821', 'telegramUsername': None, 'linkedAt': '2025-03-14T10:30:00.000Z', 'sessionActive': True, 'sessionSince': '2025-03-14T16:00:00+05:30', 'lastSeenAt': None, 'signInPausedUntil': None, 'pairingPending': False}, ['heldCount']),
    ('PairingRes', {'code': 'ABC', 'command': '/start ABC', 'expiresAt': '2025-03-14T16:00:00+05:30'}, 'same'),
    ('BotTokenReq', {'token': '123456789:AAH-abc_DEFghi123456789'}, 'same'),
    ('BotTokenReq', {'token': 'short'}, ['token']),
    ('BotTokenReq', {'token': 'xxxxxxxxxxxxxxxxxxxxxxxxx'}, ['token']),
    ('BotTokenReq', {'token': '1:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}, ['token']),
    ('BotTokenRes', {'ok': True, 'botUsername': None}, 'same'),
    ('TelegramUpdate', {'update_id': 1, 'message': {'message_id': 2, 'chat': {'id': 3, 'type': 'private', 'title': 'x'}, 'text': 'hi', 'from': {'id': 4, 'is_bot': False, 'username': 'u', 'language_code': 'en'}, 'date': 5}, 'extra': 1}, 'same'),
    ('TelegramUpdate', {'update_id': 1, 'callback_query': {'id': 'cb', 'from': {'id': 4}, 'message': {'message_id': 2, 'chat': {'id': 3, 'type': 'private'}}, 'data': 'tag:x'}}, 'same'),
    ('TelegramUpdate', {'update_id': '1'}, ['update_id']),
    ('TelegramUpdate', {'update_id': 1, 'message': {'message_id': 2}}, ['message.chat']),
    ('TelegramUpdate', {'update_id': 1, 'callback_query': {'id': 'cb'}}, ['callback_query.from']),
    ('TelegramUpdate', {}, ['update_id']),
    ('SettingsDto', {'openingBalanceMinor': 100, 'reconcileGraceHours': 6, 'alertLevel': 80, 'warnOnPace': True, 'allowReveal': True, 'sessionIdleDays': 30, 'digestMode': 'off', 'digestHour': 21, 'afterTag': 'keep', 'currency': 'INR'}, 'same'),
    ('SettingsDto', {'openingBalanceMinor': 100, 'reconcileGraceHours': 6, 'alertLevel': 80, 'warnOnPace': True, 'allowReveal': True, 'sessionIdleDays': 30, 'digestMode': 'off', 'digestHour': 21, 'afterTag': 'keep', 'currency': 'USD'}, ['currency']),
    ('SettingsDto', {'openingBalanceMinor': 100, 'reconcileGraceHours': 6, 'alertLevel': 80, 'warnOnPace': True, 'allowReveal': True, 'sessionIdleDays': 30, 'digestMode': 'off', 'digestHour': 21, 'afterTag': 'keep'}, ['currency']),
    ('SettingsDto', {'openingBalanceMinor': 100, 'reconcileGraceHours': 6, 'alertLevel': 75, 'warnOnPace': True, 'allowReveal': True, 'sessionIdleDays': 30, 'digestMode': 'off', 'digestHour': 21, 'afterTag': 'keep', 'currency': 'INR', 'extra': 1}, ['alertLevel']),
    ('SettingsPatch', {}, 'same'),
    ('SettingsPatch', {'alertLevel': 90, 'digestHour': 3, 'reconcileGraceHours': 0, 'currency': 'USD'}, {'ok': {'reconcileGraceHours': 0, 'alertLevel': 90, 'digestHour': 3}}),
    ('SettingsPatch', {'alertLevel': 91, 'afterTag': 'x'}, ['afterTag', 'alertLevel']),
    ('MeDto', {'id': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'email': 'a@b.in', 'name': None, 'timezone': 'Asia/Kolkata', 'pendingEmail': None, 'deleteAfter': None, 'alertBadgeCount': 1, 'needsLookCount': 2, 'untaggedCount': 3, 'demo': False}, 'same'),
    ('MeDto', {'id': 'any', 'email': 'e', 'name': 'n', 'timezone': 'z', 'pendingEmail': 'p', 'deleteAfter': '2025-01-01T00:00:00.000Z', 'alertBadgeCount': 1.5, 'needsLookCount': 2, 'untaggedCount': 3}, ['alertBadgeCount']),
    ('EVENT:transaction.changed', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'transactionId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'kind': 'created', 'type': 'debit', 'status': 'pending', 'source': 'captured', 'occurredAt': '2025-03-14T16:00:00+05:30', 'categoryIds': [None, '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'], 'taggedVia': None}, 'same'),
    ('EVENT:transaction.changed', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'transactionId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'kind': 'updated', 'type': 'debit', 'status': 'pending', 'source': 'captured', 'occurredAt': '2025-03-14T16:00:00+05:30', 'categoryIds': [None, '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'], 'taggedVia': 'rule', 'tz': 'Asia/Kolkata'}, 'same'),
    ('EVENT:transaction.changed', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'transactionId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'kind': 'gone', 'type': 'debit', 'status': 'pending', 'source': 'captured', 'occurredAt': '2025-03-14T16:00:00+05:30', 'categoryIds': ['x'], 'taggedVia': 'sms'}, ['categoryIds.0', 'kind', 'taggedVia']),
    ('EVENT:transaction.changed', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'transactionId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'kind': 'created', 'type': 'debit', 'status': 'pending', 'source': 'captured', 'occurredAt': '2025-03-14T16:00:00+05:30', 'categoryIds': [None, '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23']}, ['taggedVia']),
    ('EVENT:transaction.changed', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'transactionId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'kind': 'created', 'type': 'debit', 'status': 'pending', 'source': 'captured', 'occurredAt': '2025-03-14T16:00:00+05:30', 'categoryIds': [None, '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'], 'taggedVia': None, 'tz': ''}, ['tz']),
    ('EVENT:credit.added', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'transactionId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'month': '2025-03', 'amountMinor': -5, 'addToPlan': True}, 'same'),
    ('EVENT:credit.added', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'transactionId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'month': '2025-3', 'amountMinor': 5, 'addToPlan': 1}, ['addToPlan', 'month']),
    ('EVENT:alert.created', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'alertId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'budgetId': '0b7d1a52-9c3e-4f08-8d6a-5e1f2a9b4c70', 'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'categoryName': 'food', 'level': 'exceeded', 'periodKey': '2025-03', 'pct': 101}, 'same'),
    ('EVENT:alert.created', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'alertId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'budgetId': '0b7d1a52-9c3e-4f08-8d6a-5e1f2a9b4c70', 'categoryId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'categoryName': 'food', 'level': 'x', 'periodKey': '2025-03', 'pct': 1.5}, ['level', 'pct']),
    ('EVENT:unparsed.created', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'unparsedId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'failuresLast24h': 3}, 'same'),
    ('EVENT:unparsed.created', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'unparsedId': '7c9e6679-7425-40de-944b-e07fc1f90ae7'}, ['failuresLast24h']),
    ('EVENT:account.deleted', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'}, 'same'),
    ('EVENT:account.deleted', {'userId': 'x'}, ['userId']),
    ('EVENT:audit.record', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'action': 'export'}, 'same'),
    ('EVENT:audit.record', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'action': 'x', 'deviceId': None, 'ip': None, 'meta': {'a': 'b', 'n': 1, 'f': 1.5, 'ok': True, 'z': None}}, 'same'),
    ('EVENT:audit.record', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'action': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}, ['action']),
    ('EVENT:audit.record', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'action': ''}, ['action']),
    ('EVENT:audit.record', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'action': 'x', 'meta': {'a': [1]}}, ['meta.a']),
    ('EVENT:audit.record', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'action': 'x', 'deviceId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'ip': '1.2.3.4'}, 'same'),
    ('JOB:budget.evaluate', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'categoryId': '7c9e6679-7425-40de-944b-e07fc1f90ae7', 'periodKey': '2025-03'}, 'same'),
    ('JOB:budget.evaluate', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'}, ['categoryId', 'periodKey']),
    ('JOB:balance.reconcile', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'}, 'same'),
    ('JOB:balance.reconcile', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'checkId': '7c9e6679-7425-40de-944b-e07fc1f90ae7'}, 'same'),
    ('JOB:balance.reconcile', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23', 'checkId': 'x'}, ['checkId']),
    ('JOB:recurring.post', {}, 'same'),
    ('JOB:recurring.post', {'a': 1}, {'ok': {}}),
    ('JOB:telegram.send', {'promptId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'}, 'same'),
    ('JOB:telegram.send', {}, ['promptId']),
    ('JOB:telegram.sync_prompt', {'promptId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'}, 'same'),
    ('JOB:telegram.digest', {}, 'same'),
    ('JOB:telegram.digest', {'userId': '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'}, 'same'),
    ('JOB:telegram.digest', {'userId': 'x'}, ['userId']),
    ('JOB:retention.sweep', {}, 'same'),
]


def _target(name: str) -> Any:
    if name.startswith('EVENT:'):
        return C.EVENTS[name[6:]]
    if name.startswith('JOB:'):
        return C.JOBS[name[4:]]
    return getattr(C, name)


def _canon(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: _canon(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_canon(v) for v in x]
    if isinstance(x, str) and C.base._ISO_RE.fullmatch(x):
        return iso_ms(C.base._parse_iso(x))
    return x


def _run(name: str, inp: Any) -> tuple[Any, list[str] | None]:
    t = _target(name)
    ad = None if isinstance(t, type) and issubclass(t, BaseModel) else TypeAdapter(t)
    try:
        v = ad.validate_python(inp) if ad else t.model_validate(inp)
    except ValidationError as e:
        return None, sorted({'.'.join(str(p) for p in x['loc']) for x in e.errors(include_url=False)})
    return (ad.dump_python(v, mode='json', by_alias=True) if ad else dump(v)), None


def _id(row: tuple[str, Any, Any]) -> str:
    return f'{row[0]}:{json.dumps(row[1], default=str)[:60]}'


@pytest.mark.parametrize('schema,payload,expected', CORPUS, ids=[_id(r) for r in CORPUS])
def test_matches_zod(schema: str, payload: Any, expected: Any) -> None:
    out, paths = _run(schema, payload)
    if isinstance(expected, list):
        assert out is None, f'Zod rejected at {expected} but the model accepted {out}'
        assert paths == expected
    else:
        assert paths is None, f'Zod accepted but the model failed at {paths}'
        want = payload if expected == 'same' else expected['ok']
        assert _canon(out) == _canon(want)


def test_every_ts_export_exists() -> None:
    import glob
    import os
    import pathlib
    import re

    root = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'packages', 'contracts', 'src')
    renamed = {'uuid': 'Uuid', 'paise': 'Paise', 'positivePaise': 'PositivePaise', 'isoDateTime': 'IsoDateTime',
               'dateKey': 'DateKey', 'monthKey': 'MonthKey', 'tzName': 'TzName', 'eventQueue': 'event_queue',
               'sweepQueue': 'sweep_queue'}
    files = [f for f in glob.glob(os.path.join(root, '*.ts')) if not f.endswith('index.ts')]
    if not files:
        pytest.skip('TypeScript sources are gone (port finished)')
    names = [n for f in files for n in re.findall(r'^export const (\w+)', pathlib.Path(f).read_text(), re.MULTILINE)]
    assert names
    assert [n for n in names if not hasattr(C, renamed.get(n, n))] == []


# scalar types
class _Scalars(C.Model):
    paise: Paise
    positive: PositivePaise
    uid: Uuid
    at: IsoDateTime
    limit: CoerceInt = 5
    flag: StringBool = False


def _scalars(**kw: Any) -> dict[str, Any]:
    return {'paise': 1, 'positive': 1, 'uid': U1, 'at': T1, **kw}


def test_paise_is_a_safe_integer_not_a_float_or_string() -> None:
    assert _Scalars.model_validate(_scalars(paise=2**53 - 1)).paise == 2**53 - 1
    assert _Scalars.model_validate(_scalars(paise=-(2**53 - 1))).paise == -(2**53 - 1)
    assert _Scalars.model_validate(_scalars(paise=5.0)).paise == 5
    for bad in (2**53, 1.5, '5', True, None):
        with pytest.raises(ValidationError):
            _Scalars.model_validate(_scalars(paise=bad))
    with pytest.raises(ValidationError):
        _Scalars.model_validate(_scalars(positive=0))


def test_uuid_accepts_a_uuid_object_from_the_driver_and_keeps_case() -> None:
    import uuid

    assert _Scalars.model_validate(_scalars(uid=uuid.UUID(U1))).uid == U1
    assert _Scalars.model_validate(_scalars(uid=U1.upper())).uid == U1.upper()
    assert _Scalars.model_validate(_scalars(uid='00000000-0000-0000-0000-000000000000'))
    with pytest.raises(ValidationError):
        _Scalars.model_validate(_scalars(uid='3f2b8c1e-5d4a-0b7e-9a10-2c6d8e0f1a23'))  # version 0


def test_iso_datetime_is_aware_in_memory_and_millisecond_z_on_the_wire() -> None:
    m = _Scalars.model_validate(_scalars(at='2025-03-14T16:00:00+05:30'))
    assert m.at == datetime(2025, 3, 14, 10, 30, tzinfo=UTC) and m.at.utcoffset() == timedelta(0)
    assert dump(m)['at'] == '2025-03-14T10:30:00.000Z'
    assert dump(_Scalars.model_validate(_scalars(at='2025-03-14T10:30:00.123456Z')))['at'] == '2025-03-14T10:30:00.123Z'
    ist = datetime(2025, 3, 14, 16, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert dump(_Scalars.model_validate(_scalars(at=ist)))['at'] == '2025-03-14T10:30:00.000Z'
    for bad in ('2025-03-14T10:30:00', '2025-03-14', '2025-02-30T10:00:00Z', datetime(2025, 1, 1), 5):
        with pytest.raises(ValidationError):
            _Scalars.model_validate(_scalars(at=bad))


def test_coerce_int_and_string_bool_follow_zod_for_query_strings() -> None:
    assert _Scalars.model_validate(_scalars(limit=' 7 ')).limit == 7
    assert _Scalars.model_validate(_scalars(limit='1e1')).limit == 10
    assert _Scalars.model_validate(_scalars(limit='')).limit == 0
    for bad in ('1.5', 'abc', 'nan', '1_0'):
        with pytest.raises(ValidationError):
            _Scalars.model_validate(_scalars(limit=bad))
    for word in ('true', 'TRUE', '1', 'yes', 'on', 'y', 'enabled'):
        assert _Scalars.model_validate(_scalars(flag=word)).flag is True
    for word in ('false', 'False', '0', 'no', 'off', 'n', 'disabled'):
        assert _Scalars.model_validate(_scalars(flag=word)).flag is False
    with pytest.raises(ValidationError):
        _Scalars.model_validate(_scalars(flag='maybe'))


# optional keys, defaults, transforms
def test_optional_keys_are_left_out_and_explicit_null_is_kept_only_where_nullable() -> None:
    req = C.IngestTransactionReq.model_validate(
        {'type': 'debit', 'amountMinor': 5, 'occurredAt': T1, 'deviceId': U1, 'capturedAt': T1, 'dedupeKey': 'k'}
    )
    out = dump(req)
    assert 'payee' not in out and 'reference' not in out and 'balanceAfterMinor' not in out
    assert out['weakParse'] is False and out['reversal'] is False
    with_null = C.IngestTransactionReq.model_validate({**out, 'payee': None})
    assert dump(with_null)['payee'] is None
    # python-side construction by snake_case names gives the same JSON
    built = C.IngestTransactionReq(type='debit', amount_minor=5, occurred_at=T1, device_id=U1, captured_at=T1, dedupe_key='k')
    assert dump(built) == out
    # a plain `.optional()` field never prints null
    assert 'createdAt' not in dump(C.UserDto(id=U1, email='a@b.in', name=None, timezone='x', pending_email=None, delete_after=None))
    assert dump(C.ErrorBody.model_validate({'error': {'code': 'x', 'message': 'm'}})) == {'error': {'code': 'x', 'message': 'm'}}


def test_defaults_stay_on_the_model() -> None:
    assert dump(C.TagReq(tag='x')) == {'tag': 'x', 'via': 'web'}
    assert C.SessionCheckRes(valid=True).limited is False
    rule = C.RecurringRuleDto.model_validate({
        'id': U1, 'name': 'Rent', 'categoryId': U1, 'categoryName': 'rent', 'amountMinor': 5,
        'schedule': {'kind': 'weekly', 'weekday': 1}, 'nextDue': '2025-04-01', 'paused': False, 'endsOn': None,
    })
    assert (rule.note, rule.match_hint, rule.active) == (None, None, True)
    out = dump(rule)
    assert out['note'] is None and out['matchHint'] is None and out['active'] is True
    assert C.TransactionsQuery().limit == 8 and C.TransactionsQuery().src == 'all'
    assert C.AuditQuery().limit == 50 and C.MonthsQuery(end='2025-03').count == 6
    assert C.CreditReq(amount_minor=1, date='2025-03-01', tag='t').add_to_plan is True
    assert C.BudgetCreateReq(tag='t', limit_minor=5).period == 'monthly'


def test_email_input_trims_lowercases_then_checks_the_address() -> None:
    assert TypeAdapter(C.EmailInput).validate_python('  Foo@Bar.COM ') == 'foo@bar.com'
    for bad in ('nope', 'a@b', '@b.co', 'a b@c.co'):
        with pytest.raises(ValidationError):
            TypeAdapter(C.EmailInput).validate_python(bad)
    assert C.RegisterReq(email=' A@B.IN ', password='x', name='  Asha ').name == 'Asha'


def test_extra_keys_are_ignored_except_for_loose_telegram_objects() -> None:
    assert 'zzz' not in dump(C.CategoryDto.model_validate({'id': U1, 'name': 'x', 'archived': False, 'zzz': 1}))
    upd = C.TelegramUpdate.model_validate({
        'update_id': 1, 'extra': {'a': 1},
        'message': {'message_id': 2, 'chat': {'id': 3, 'type': 'private', 'title': 't'}, 'from': {'id': 4, 'language_code': 'en'}},
    })
    out = dump(upd)
    assert out['extra'] == {'a': 1} and out['message']['from'] == {'id': 4, 'language_code': 'en'}
    assert upd.message.from_.id == 4  # type: ignore[union-attr]


# refinements and error paths
def test_refine_errors_carry_zod_messages_and_paths() -> None:
    with pytest.raises(ValidationError) as e:
        C.BudgetCreateReq.model_validate({})
    assert validation_details(e.value) == {
        'categoryId': 'Give either categoryId or tag',
        'limitMinor': 'Give a limit, or use the month allocation',
    }
    with pytest.raises(ValidationError) as e:
        C.TagReq.model_validate({})
    assert validation_details(e.value) == {'_': 'give either tag or categoryId'}
    with pytest.raises(ValidationError) as e:
        C.PlanPutReq.model_validate({'totalMinor': 1, 'lines': [{'allocatedMinor': 1}]})
    assert validation_details(e.value) == {'lines.0.categoryId': 'Give either categoryId or tag'}
    with pytest.raises(ValidationError) as e:
        C.TwoFactorVerifyReq.model_validate({'twoFactorToken': 'x' * 12})
    assert validation_details(e.value) == {'_': 'Send exactly one of code, recoveryCode, passkey'}
    with pytest.raises(ValidationError) as e:
        C.VerifyTotpReq.model_validate({'code': '12345'})
    assert 'code' in validation_details(e.value)
    with pytest.raises(ValidationError) as e:
        C.ConfirmEmailReq.model_validate({'token': 'short'})
    assert validation_details(e.value) == {'token': 'Too small: expected string to have >=10 characters'}


def test_custom_regex_messages_match_zod() -> None:
    with pytest.raises(ValidationError) as e:
        C.TwoFactorEnableConfirmReq.model_validate({'code': 'abc'})
    assert validation_details(e.value) == {'code': 'Enter the 6-digit code'}
    with pytest.raises(ValidationError) as e:
        C.SummaryQuery.model_validate({'month': '2025-13'})
    assert validation_details(e.value) == {'month': 'YYYY-MM'}
    with pytest.raises(ValidationError) as e:
        C.CreditReq.model_validate({'amountMinor': 1, 'date': '14/03/2025', 'tag': 't'})
    assert validation_details(e.value) == {'date': 'YYYY-MM-DD'}
    with pytest.raises(ValidationError) as e:
        C.BotTokenReq.model_validate({'token': 'x' * 25})
    assert validation_details(e.value) == {'token': 'That does not look like a bot token'}


def test_null_for_an_optional_field_is_read_as_absent_in_models_but_rejected_in_patches() -> None:
    # Deliberate difference: models built in Python pass None for "not given"; a Zod `.optional()` would refuse null.
    assert dump(C.TagReq.model_validate({'tag': 'a', 'categoryId': None})) == {'tag': 'a', 'via': 'web'}
    for patch, key in ((C.TransactionSettingsPatch, 'reconcileGraceHours'), (C.PlanningSettingsPatch, 'warnOnPace'), (C.TelegramSettingsPatch, 'digestMode')):
        with pytest.raises(ValidationError) as e:
            patch.model_validate({key: None})
        assert key in validation_details(e.value)


def test_patch_models_know_which_keys_an_empty_request_really_has() -> None:
    assert C.BudgetPatchReq.model_validate({'warnPct': None}).present_keys() == {'warn_pct'}
    with pytest.raises(ValidationError):
        C.BudgetPatchReq.model_validate({})
    assert C.PatchRecurringReq.model_validate({'endsOn': None}).present_keys() == {'ends_on'}
    assert dump(C.PatchRecurringReq.model_validate({'endsOn': None, 'paused': True})) == {'endsOn': None, 'paused': True}


# unions
def test_schedule_union_dispatches_on_kind_and_reports_zod_paths() -> None:
    s = C.ScheduleAdapter.validate_python({'kind': 'yearly', 'month': 12, 'day': 25})
    assert isinstance(s, C.YearlySchedule) and dump(s) == {'kind': 'yearly', 'month': 12, 'day': 25}
    assert isinstance(C.ScheduleAdapter.validate_python({'kind': 'weekly', 'weekday': 0}), C.WeeklySchedule)
    with pytest.raises(ValidationError) as e:
        C.CreateRecurringReq.model_validate({'name': 'n', 'tag': 't', 'amountMinor': 1, 'schedule': {'kind': 'daily'}})
    assert validation_details(e.value) == {'schedule.kind': "Invalid discriminator value. Expected 'monthly' | 'weekly' | 'yearly'"}
    with pytest.raises(ValidationError) as e:
        C.CreateRecurringReq.model_validate({'name': 'n', 'tag': 't', 'amountMinor': 1, 'schedule': {'kind': 'monthly', 'day': 32}})
    assert list(validation_details(e.value)) == ['schedule.day']


def test_attention_items_round_trip_by_kind() -> None:
    items = [
        {'kind': 'limit', 'category': 'Fun', 'pct': 85, 'status': 'close'},
        {'kind': 'untagged', 'count': 3},
        {'kind': 'needs_look', 'count': 1},
        {'kind': 'unaccounted', 'count': 1},
        {'kind': 'recurring', 'name': 'Rent', 'amount': 100, 'due': '2025-04-01'},
    ]
    ad = TypeAdapter(list[C.AttentionItem])
    assert ad.dump_python(ad.validate_python(items), mode='json', by_alias=True) == items


# settings composition
def test_settings_are_composed_from_the_owners_and_patch_keys_say_who_takes_what() -> None:
    assert patch_keys(C.TransactionSettingsPatch) == ['openingBalanceMinor', 'reconcileGraceHours']
    assert patch_keys(C.PlanningSettingsPatch) == ['alertLevel', 'warnOnPace']
    assert patch_keys(C.TelegramSettingsPatch) == ['allowReveal', 'sessionIdleDays', 'digestMode', 'digestHour', 'afterTag']
    assert patch_keys(C.SettingsDto) == [
        *patch_keys(C.TransactionSettingsPatch), *patch_keys(C.PlanningSettingsPatch), *patch_keys(C.TelegramSettingsPatch), 'currency',
    ]
    assert patch_keys(C.SettingsPatch) == patch_keys(C.SettingsDto)[:-1]
    # a patch with a key nobody owns (currency) drops it, like a non-strict z.object
    assert dump(C.SettingsPatch.model_validate({'alertLevel': 70, 'currency': 'USD'})) == {'alertLevel': 70}
    assert dump(C.SettingsPatch.model_validate({})) == {}


# events, jobs, routes
def test_event_and_job_catalogue_matches_ts() -> None:
    assert list(C.EVENTS) == ['transaction.changed', 'credit.added', 'alert.created', 'unparsed.created', 'account.deleted', 'audit.record']
    assert list(C.JOBS) == ['budget.evaluate', 'balance.reconcile', 'recurring.post', 'telegram.send', 'telegram.sync_prompt', 'telegram.digest', 'retention.sweep']
    assert set(C.EVENTS) == set(get_args(C.EventName)) and set(C.JOBS) == set(get_args(C.JobName))
    assert C.SUBSCRIPTIONS == {
        'transaction.changed': ('planning', 'telegram'),
        'credit.added': ('planning',),
        'alert.created': ('telegram',),
        'unparsed.created': ('telegram',),
        'account.deleted': ('transactions', 'ingest', 'planning', 'recurring', 'telegram'),
        'audit.record': ('auth',),
    }
    assert set(C.SUBSCRIPTIONS) == set(C.EVENTS)
    assert C.event_queue('planning', 'transaction.changed') == 'planning.transaction.changed'
    assert C.sweep_queue('transactions') == 'retention.sweep.transactions'


def test_event_payload_dump_is_the_outbox_json() -> None:
    p = C.EVENTS['transaction.changed'].model_validate({
        'userId': U1, 'transactionId': U2, 'kind': 'created', 'type': 'debit', 'status': 'pending', 'source': 'captured',
        'occurredAt': datetime(2025, 3, 14, 10, 30, tzinfo=UTC), 'categoryIds': [None, U1], 'taggedVia': None,
    })
    assert dump(p) == {
        'userId': U1, 'transactionId': U2, 'kind': 'created', 'type': 'debit', 'status': 'pending', 'source': 'captured',
        'occurredAt': T1, 'categoryIds': [None, U1], 'taggedVia': None,
    }
    assert dump(C.EVENTS['unparsed.created'](user_id=U1, unparsed_id=U2, failures_last24h=3)) == {
        'userId': U1, 'unparsedId': U2, 'failuresLast24h': 3,
    }
    assert dump(C.JOBS['recurring.post']()) == {} and dump(C.JOBS['telegram.digest']()) == {}


def test_route_table_and_public_paths() -> None:
    assert C.API_PREFIX == '/api'
    assert len(C.ROUTE_TABLE) == 19
    assert ('/balance-check', 'transactions') in C.ROUTE_TABLE and ('/me/email', 'auth') in C.ROUTE_TABLE
    assert dict(C.ROUTE_TABLE)['/dashboard'] == 'reports' and dict(C.ROUTE_TABLE)['/telegram'] == 'telegram'
    assert '/ingest/message' in C.PUBLIC_PATHS and '/telegram/webhook/*' in C.PUBLIC_PATHS and len(C.PUBLIC_PATHS) == 10
    assert list(C.CSRF_EXEMPT_PATHS) == list(C.PUBLIC_PATHS)


def test_models_build_from_database_rows_and_dump_camel_case() -> None:
    row = {
        'id': U1, 'type': 'debit', 'amount_minor': 45000, 'occurred_at': datetime(2025, 3, 14, 10, 30, tzinfo=UTC),
        'payee': 'Swiggy', 'description': None, 'category_id': U2, 'category_name': 'food', 'source': 'captured',
        'status': 'confirmed', 'recurring_id': None, 'captured_at': None, 'weak_parse': False, 'unrelated_column': 1,
    }
    assert dump(C.TransactionDto.model_validate(row)) == {
        'id': U1, 'type': 'debit', 'amountMinor': 45000, 'occurredAt': T1, 'payee': 'Swiggy', 'description': None,
        'categoryId': U2, 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None,
        'capturedAt': None, 'weakParse': False,
    }
    # `z.string()` time fields accept the datetime a row holds
    u = C.UserDto.model_validate({'id': U1, 'email': 'a@b.in', 'name': None, 'timezone': 'x', 'pending_email': None,
                                  'delete_after': datetime(2025, 3, 21, tzinfo=UTC), 'created_at': datetime(2025, 3, 14, tzinfo=UTC)})
    assert dump(u)['deleteAfter'] == '2025-03-21T00:00:00.000Z'
