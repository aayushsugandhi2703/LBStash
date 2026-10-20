"""Service clients: URLs, methods, queries, bodies, token, retries, error mapping, shape checks."""

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qsl

import httpx
import jwt
import lbstash.contracts as C
import pytest
from lbstash.clients import CallAs, ClientOptions, TransactionsClient, create_clients
from lbstash.common import AppError, Ctx
from lbstash.crypto import verify_internal_token

SECRET = 'test-internal-secret-0123456789abcdef'
U1 = '3f2b8c1e-5d4a-4b7e-9a10-2c6d8e0f1a23'
U2 = '7c9e6679-7425-40de-944b-e07fc1f90ae7'
T1 = '2025-03-14T10:30:00.000Z'
ENV = SimpleNamespace(
    INTERNAL_SECRET=SECRET,
    AUTH_URL='http://auth:3001',
    TRANSACTIONS_URL='http://transactions:3002',
    INGEST_URL='http://ingest:3003',
    PLANNING_URL='http://planning:3004',
    RECURRING_URL='http://recurring:3005',
    TELEGRAM_URL='http://telegram:3007',
)
AS = CallAs(user_id=U1, tz='Asia/Kolkata', request_id='req-1')

TX = {
    'id': U1, 'type': 'debit', 'amountMinor': 45000, 'occurredAt': T1, 'payee': 'Swiggy', 'description': None,
    'categoryId': U2, 'categoryName': 'food', 'source': 'captured', 'status': 'confirmed', 'recurringId': None,
    'capturedAt': T1, 'weakParse': False,
}
CAT = {'id': U2, 'name': 'food', 'archived': False}
USER = {'id': U1, 'email': 'a@b.in', 'name': None, 'timezone': 'Asia/Kolkata', 'pendingEmail': None, 'deleteAfter': None}
STAT = {'categoryId': U2, 'categoryName': 'food', 'archived': False, 'count': 1, 'spentMinor': 5, 'receivedMinor': 0}
CHECK = {
    'id': U1, 'bankBalanceMinor': 1, 'transactionsBalanceMinor': 2, 'gapMinor': -1, 'source': 'message', 'status': 'open',
    'checkedAt': T1, 'asOf': T1, 'transactionId': None, 'graceEndsAt': None,
}
LINE = {'categoryId': U2, 'categoryName': 'food', 'allocatedMinor': 5, 'spentMinor': 1}
PLAN = {'month': '2025-03', 'totalMinor': 10, 'lines': [LINE], 'assignedMinor': 5, 'unassignedMinor': 5}
BUDGET = {
    'id': U1, 'categoryId': U2, 'categoryName': 'food', 'limitMinor': 10, 'period': 'monthly', 'warnPct': None,
    'active': True, 'spentMinor': 1, 'pct': 10, 'projectedMinor': 3, 'status': 'ok',
}
ALERT = {
    'id': U1, 'budgetId': U2, 'categoryName': 'food', 'level': 'alert', 'periodKey': '2025-03',
    'sentAt': T1, 'readAt': None,
}
RULE = {
    'id': U1, 'name': 'Rent', 'categoryId': U2, 'categoryName': 'rent', 'amountMinor': 5,
    'schedule': {'kind': 'monthly', 'day': 1}, 'nextDue': '2025-04-01', 'paused': False, 'endsOn': None,
}
TAG_RES = {
    'transaction': TX, 'changed': True, 'previousCategoryId': None, 'alsoTaggedIds': [], 'categoryCreated': False,
}
TRANSACTIONS_SETTINGS = {'openingBalanceMinor': 1, 'reconcileGraceHours': 6}
PLANNING_SETTINGS = {'alertLevel': 80, 'warnOnPace': True}
TELEGRAM_SETTINGS = {
    'allowReveal': True, 'sessionIdleDays': 30, 'digestMode': 'off', 'digestHour': 21, 'afterTag': 'keep',
}
EXPORT = {'service': 'x', 'tables': {'t': [{'a': 1}]}}
ING_REQ = {
    'type': 'debit', 'amountMinor': 5, 'occurredAt': T1, 'deviceId': U1, 'capturedAt': T1, 'dedupeKey': 'k',
    'weakParse': False, 'reversal': False,
}


class Recorder:
    """A MockTransport that records every request and answers from a queue (the last answer repeats)."""

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        a = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(a, Exception):
            raise a
        if isinstance(a, httpx.Response):
            return a
        status, body = a if isinstance(a, tuple) else (200, a)
        return httpx.Response(status, json=body) if body is not None else httpx.Response(status)

    async def sleep(self, s: float) -> None:
        self.sleeps.append(s)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]


def make(*answers: Any, **extra: Any) -> tuple[Any, Recorder]:
    rec = Recorder(*answers)
    clients = create_clients('planning', ENV, transport=httpx.MockTransport(rec), sleep=rec.sleep, **extra)
    return clients, rec


def query(req: httpx.Request) -> dict[str, str]:
    return dict(parse_qsl(req.url.query.decode()))


def body(req: httpx.Request) -> Any:
    return json.loads(req.content)


# every method: method, URL, query, body, validated type
CASES: list[tuple[str, str, tuple[Any, ...], dict[str, Any], str, str, dict[str, str], Any, Any, type]] = [
    # (client, method name, args, kwargs, HTTP method, path, query, request body, response, model)
    ('transactions', 'ingest', (ING_REQ,), {}, 'POST', '/internal/transactions/ingest', {}, ING_REQ, {'outcome': 'created', 'transaction': TX}, C.IngestTransactionRes),
    ('transactions', 'create_manual', ({'type': 'credit', 'amountMinor': 1, 'occurredAt': T1},), {}, 'POST', '/internal/transactions/manual', {}, {'type': 'credit', 'amountMinor': 1, 'occurredAt': T1}, {'transaction': TX}, C.TransactionRes),
    ('transactions', 'post_recurring', ({'ruleId': U1, 'name': 'Rent', 'categoryId': U2, 'amountMinor': 5, 'dueDate': '2025-04-01'},), {}, 'POST', '/internal/transactions/recurring', {}, {'ruleId': U1, 'name': 'Rent', 'categoryId': U2, 'amountMinor': 5, 'dueDate': '2025-04-01'}, {'outcome': 'posted', 'transaction': TX}, C.RecurringPostRes),
    ('transactions', 'get_transaction', (U2,), {}, 'GET', f'/internal/transactions/{U2}', {}, None, {'transaction': TX}, C.TransactionRes),
    ('transactions', 'tag', (U2, {'tag': 'food', 'via': 'telegram'}), {}, 'POST', f'/internal/transactions/{U2}/tag', {}, {'tag': 'food', 'via': 'telegram'}, TAG_RES, C.TagRes),
    ('transactions', 'pending', (), {}, 'GET', '/internal/transactions/pending', {'limit': '50'}, None, {'count': 1, 'items': [TX]}, C.PendingRes),
    ('transactions', 'pending', (5,), {}, 'GET', '/internal/transactions/pending', {'limit': '5'}, None, {'count': 0, 'items': []}, C.PendingRes),
    ('transactions', 'categories', (), {}, 'GET', '/internal/categories', {}, None, {'items': [CAT]}, C.CategoriesRes),
    ('transactions', 'categories', (), {'sort': 'usage', 'limit': 6, 'include_archived': True}, 'GET', '/internal/categories', {'sort': 'usage', 'limit': '6', 'includeArchived': 'true'}, None, {'items': [CAT]}, C.CategoriesRes),
    ('transactions', 'resolve_category', ('food',), {}, 'POST', '/internal/categories/resolve', {}, {'tag': 'food'}, {'category': CAT, 'created': True}, C.ResolveCategoryRes),
    ('transactions', 'spend_by_category', ('2025-03-01T00:00:00.000Z', '2025-04-01T00:00:00.000Z'), {}, 'GET', '/internal/spend/by-category', {'from': '2025-03-01T00:00:00.000Z', 'to': '2025-04-01T00:00:00.000Z'}, None, {'items': [{'categoryId': None, 'categoryName': None, 'spentMinor': 5}]}, C.SpendByCategoryRes),
    ('transactions', 'month_summary', ('2025-03',), {}, 'GET', '/internal/aggregates/summary', {'month': '2025-03'}, None, {'month': '2025-03', 'carriedOverMinor': 1, 'incomeMinor': 2, 'spentMinor': 3, 'availableMinor': 4, 'untaggedCount': 0, 'unaccountedCount': 0, 'lastCapturedAt': None}, C.MonthSummaryRes),
    ('transactions', 'months', ('2025-03',), {}, 'GET', '/internal/aggregates/months', {'end': '2025-03', 'count': '6'}, None, {'items': [{'month': '2025-03', 'incomeMinor': 1, 'spentMinor': 2, 'closingMinor': 3}]}, C.MonthsRes),
    ('transactions', 'months', ('2025-03', 12), {}, 'GET', '/internal/aggregates/months', {'end': '2025-03', 'count': '12'}, None, {'items': []}, C.MonthsRes),
    ('transactions', 'category_months', ('2025-03', 3), {}, 'GET', '/internal/aggregates/category-months', {'end': '2025-03', 'count': '3'}, None, {'items': [{'month': '2025-03', 'categoryId': U2, 'categoryName': 'food', 'spentMinor': 1}]}, C.CategoryMonthsRes),
    ('transactions', 'daily', ('2025-03',), {}, 'GET', '/internal/aggregates/daily', {'month': '2025-03'}, None, {'items': [{'day': '2025-03-01', 'spentMinor': 1}]}, C.DailyRes),
    ('transactions', 'daily', ('2025-03', [U1, U2]), {}, 'GET', '/internal/aggregates/daily', {'month': '2025-03', 'excludeCategoryIds': f'{U1},{U2}'}, None, {'items': []}, C.DailyRes),
    ('transactions', 'balance_checks', (), {}, 'GET', '/balance-checks', {'limit': '1'}, None, {'items': [CHECK]}, C.BalanceChecksRes),
    ('transactions', 'balance_checks', (10,), {}, 'GET', '/balance-checks', {'limit': '10'}, None, {'items': []}, C.BalanceChecksRes),
    ('transactions', 'settings', (), {}, 'GET', '/internal/settings', {}, None, TRANSACTIONS_SETTINGS, C.TransactionSettings),
    ('transactions', 'export', (), {}, 'GET', '/internal/export', {}, None, EXPORT, C.ExportPart),
    ('transactions', 'patch_settings', ({'reconcileGraceHours': 0},), {}, 'PATCH', '/internal/settings', {}, {'reconcileGraceHours': 0}, TRANSACTIONS_SETTINGS, C.TransactionSettings),
    ('auth', 'verify_totp', ('123456',), {}, 'POST', '/internal/totp/verify', {}, {'code': '123456'}, {'ok': True}, C.VerifyTotpRes),
    ('auth', 'me', (), {}, 'GET', '/internal/me', {}, None, {'user': USER}, C.MeInternalRes),
    ('planning', 'plan', ('2025-03',), {}, 'GET', '/plans/2025-03', {}, None, PLAN, C.PlanWithSpendDto),
    ('planning', 'budgets', ('2025-03',), {}, 'GET', '/budgets', {'month': '2025-03'}, None, {'month': '2025-03', 'alertLevel': 80, 'items': [BUDGET]}, C.BudgetsRes),
    ('planning', 'alerts', (), {}, 'GET', '/alerts', {}, None, {'unreadCount': 1, 'items': [ALERT]}, C.AlertsRes),
    ('planning', 'add_credit_to_plan', ('2025-03', {'transactionId': U1, 'amountMinor': 5}), {}, 'POST', '/internal/plans/2025-03/credit', {}, {'transactionId': U1, 'amountMinor': 5}, {'totalMinor': 15}, C.PlanCreditRes),
    ('planning', 'settings', (), {}, 'GET', '/internal/settings', {}, None, PLANNING_SETTINGS, C.PlanningSettings),
    ('planning', 'export', (), {}, 'GET', '/internal/export', {}, None, EXPORT, C.ExportPart),
    ('planning', 'patch_settings', ({'alertLevel': 90},), {}, 'PATCH', '/internal/settings', {}, {'alertLevel': 90}, PLANNING_SETTINGS, C.PlanningSettings),
    ('recurring', 'list', (), {}, 'GET', '/recurring', {}, None, {'items': [RULE], 'committedMinor': 5}, C.RecurringRes),
    ('recurring', 'export', (), {}, 'GET', '/internal/export', {}, None, EXPORT, C.ExportPart),
    ('ingest', 'unparsed_count', (), {}, 'GET', '/internal/unparsed/count', {}, None, {'open': 2}, C.UnparsedCountRes),
    ('ingest', 'export', (), {}, 'GET', '/internal/export', {}, None, EXPORT, C.ExportPart),
    ('telegram', 'settings', (), {}, 'GET', '/internal/settings', {}, None, TELEGRAM_SETTINGS, C.TelegramSettings),
    ('telegram', 'export', (), {}, 'GET', '/internal/export', {}, None, EXPORT, C.ExportPart),
    ('telegram', 'patch_settings', ({'digestHour': 7},), {}, 'PATCH', '/internal/settings', {}, {'digestHour': 7}, TELEGRAM_SETTINGS, C.TelegramSettings),
]


@pytest.mark.parametrize(
    'client,name,args,kwargs,http,path,qs,req_body,res,model', CASES, ids=[f'{c[0]}.{c[1]}-{i}' for i, c in enumerate(CASES)]
)
async def test_method_calls_the_right_endpoint(client, name, args, kwargs, http, path, qs, req_body, res, model) -> None:  # type: ignore[no-untyped-def]
    clients, rec = make(res)
    out = await getattr(getattr(clients, client), name)(AS, *args, **kwargs)
    assert isinstance(out, model)
    assert C.dump(out) == C.dump(model.model_validate(res))
    req = rec.last
    assert len(rec.requests) == 1
    assert req.method == http
    assert req.url.path == path
    assert req.url.host == {'transactions': 'transactions', 'auth': 'auth', 'planning': 'planning', 'recurring': 'recurring', 'ingest': 'ingest', 'telegram': 'telegram'}[client]
    assert query(req) == qs
    if req_body is None:
        assert req.content == b'' and 'content-type' not in req.headers
    else:
        assert body(req) == req_body and req.headers['content-type'] == 'application/json'


async def test_check_session_carries_no_user() -> None:
    clients, rec = make({'valid': True, 'limited': False})
    out = await clients.auth.check_session(U1)
    assert out.valid is True and out.limited is False
    assert rec.last.method == 'POST' and rec.last.url.path == '/internal/sessions/check' and body(rec.last) == {'sid': U1, 'ip': None}
    claims = verify_internal_token(SECRET, rec.last.headers['x-internal-token'])
    assert claims.svc == 'planning' and claims.user_id is None and claims.tz is None and claims.request_id is None
    assert 'x-request-id' not in rec.last.headers
    await clients.auth.check_session(U1, '203.0.113.7')
    assert body(rec.last) == {'sid': U1, 'ip': '203.0.113.7'}


# token and headers
async def test_each_request_carries_a_fresh_60_second_token_for_the_user() -> None:
    clients, rec = make({'items': [], 'committedMinor': 0})
    await clients.recurring.list(AS)
    token = rec.last.headers['x-internal-token']
    claims = verify_internal_token(SECRET, token)
    assert (claims.svc, claims.user_id, claims.tz, claims.request_id, claims.proxied) == ('planning', U1, 'Asia/Kolkata', 'req-1', False)
    raw = jwt.decode(token, SECRET, algorithms=['HS256'], audience=None, options={'verify_aud': False})
    assert 55 <= raw['exp'] - raw['iat'] <= 65
    assert rec.last.headers['x-request-id'] == 'req-1'


async def test_accepts_a_ctx_dict_or_none_for_who() -> None:
    clients, rec = make({'open': 0})
    await clients.ingest.unparsed_count(Ctx(user_id=U2, tz='UTC', request_id='r2'))
    claims = verify_internal_token(SECRET, rec.last.headers['x-internal-token'])
    assert (claims.user_id, claims.tz, claims.request_id) == (U2, 'UTC', 'r2')
    await clients.ingest.unparsed_count({'user_id': U1})
    assert verify_internal_token(SECRET, rec.last.headers['x-internal-token']).user_id == U1
    await clients.ingest.unparsed_count(None)
    assert verify_internal_token(SECRET, rec.last.headers['x-internal-token']).user_id is None


async def test_token_is_signed_with_the_shared_secret_only() -> None:
    clients, rec = make({'open': 0})
    await clients.ingest.unparsed_count(AS)
    with pytest.raises(Exception):  # noqa: B017  (TokenError)
        verify_internal_token('another-secret-another-secret-123456', rec.last.headers['x-internal-token'])


# request encoding
async def test_model_bodies_are_dumped_camel_case_without_absent_optionals() -> None:
    clients, rec = make({'outcome': 'duplicate', 'transaction': None})
    req = C.IngestTransactionReq(type='debit', amount_minor=5, occurred_at=T1, device_id=U1, captured_at=T1, dedupe_key='k')
    await clients.transactions.ingest(AS, req)
    assert body(rec.last) == ING_REQ and b' ' not in rec.last.content
    await clients.transactions.ingest(AS, C.IngestTransactionReq(**{**req.model_dump(), 'payee': None, 'balance_after_minor': -3}))
    assert body(rec.last)['payee'] is None and body(rec.last)['balanceAfterMinor'] == -3
    clients, rec = make(TAG_RES)
    await clients.transactions.tag(AS, U1, C.TagReq(category_id=U2))
    assert body(rec.last) == {'categoryId': U2, 'via': 'web'}


async def test_query_values_are_formatted_like_js() -> None:
    clients, rec = make({'items': [{'categoryId': None, 'categoryName': None, 'spentMinor': 1}]})
    await clients.transactions.spend_by_category(
        AS, datetime(2025, 3, 1, tzinfo=UTC), datetime(2025, 4, 1, 18, 30, tzinfo=UTC)
    )
    assert query(rec.last) == {'from': '2025-03-01T00:00:00.000Z', 'to': '2025-04-01T18:30:00.000Z'}
    assert '%3A' in rec.last.url.query.decode()  # URLSearchParams escapes ':'
    clients, rec = make({'items': []})
    await clients.transactions.categories(AS, include_archived=False)
    assert query(rec.last) == {'includeArchived': 'false'}


# retries
async def test_get_retries_5xx_with_backoff_then_succeeds() -> None:
    err = (503, {'error': {'code': 'upstream_failed', 'message': 'down'}})
    clients, rec = make(err, err, {'open': 4})
    out = await clients.ingest.unparsed_count(AS)
    assert out.open == 4 and len(rec.requests) == 3
    assert rec.sleeps == [0.1, 0.2]


async def test_get_retries_network_errors() -> None:
    clients, rec = make(httpx.ConnectError('refused'), {'open': 1})
    assert (await clients.ingest.unparsed_count(AS)).open == 1
    assert len(rec.requests) == 2 and rec.sleeps == [0.1]


async def test_get_gives_up_after_retries_and_returns_the_last_upstream_error() -> None:
    clients, rec = make((503, {'error': {'code': 'upstream_failed', 'message': 'down'}}))
    with pytest.raises(AppError) as e:
        await clients.ingest.unparsed_count(AS)
    assert e.value.status == 503 and e.value.code == 'upstream_failed' and e.value.message == 'down'
    assert len(rec.requests) == 3 and rec.sleeps == [0.1, 0.2]


async def test_unreachable_service_is_502_upstream_failed() -> None:
    clients, rec = make(httpx.ConnectError('refused'))
    with pytest.raises(AppError) as e:
        await clients.transactions.settings(AS)
    assert (e.value.status, e.value.code, e.value.message) == (502, 'upstream_failed', 'transactions is not reachable')
    assert e.value.details == {'service': 'transactions'}
    assert len(rec.requests) == 3


async def test_retries_option_changes_the_number_of_attempts() -> None:
    clients, rec = make(httpx.ConnectError('x'), retries=0)
    with pytest.raises(AppError):
        await clients.transactions.settings(AS)
    assert len(rec.requests) == 1 and rec.sleeps == []


async def test_writes_are_never_retried() -> None:
    clients, rec = make((503, {'error': {'code': 'upstream_failed', 'message': 'down'}}))
    with pytest.raises(AppError) as e:
        await clients.transactions.ingest(AS, ING_REQ)
    assert e.value.status == 503 and len(rec.requests) == 1 and rec.sleeps == []
    clients, rec = make(httpx.ReadError('boom'))
    with pytest.raises(AppError):
        await clients.transactions.resolve_category(AS, 'x')
    assert len(rec.requests) == 1


async def test_client_errors_are_not_retried() -> None:
    clients, rec = make((404, {'error': {'code': 'not_found', 'message': 'Item not found'}}))
    with pytest.raises(AppError):
        await clients.transactions.get_transaction(AS, U1)
    assert len(rec.requests) == 1 and rec.sleeps == []


# error mapping
async def test_error_bodies_come_back_as_app_errors_with_the_upstream_status() -> None:
    clients, _ = make((404, {'error': {'code': 'not_found', 'message': 'Item not found', 'details': {'id': U1}}}))
    with pytest.raises(AppError) as e:
        await clients.transactions.get_transaction(AS, U1)
    assert (e.value.status, e.value.code, e.value.message, e.value.details) == (404, 'not_found', 'Item not found', {'id': U1})
    assert e.value.to_json() == {'error': {'code': 'not_found', 'message': 'Item not found', 'details': {'id': U1}}}


async def test_two_factor_and_locked_details_survive_the_hop() -> None:
    clients, _ = make((401, {'error': {'code': 'two_factor_invalid', 'message': 'That code did not work', 'details': {'attemptsLeft': 2}}}))
    with pytest.raises(AppError) as e:
        await clients.auth.verify_totp(AS, '123456')
    assert (e.value.status, e.value.code, e.value.details) == (401, 'two_factor_invalid', {'attemptsLeft': 2})
    clients, _ = make((423, {'error': {'code': 'locked', 'message': 'Temporarily locked', 'details': {'retryAfterSeconds': 30}}}))
    with pytest.raises(AppError) as e:
        await clients.auth.verify_totp(AS, '123456')
    assert (e.value.status, e.value.code, e.value.details) == (423, 'locked', {'retryAfterSeconds': 30})


async def test_error_without_a_usable_body_gets_a_default_code_and_message() -> None:
    clients, _ = make(httpx.Response(400, text='nope'))
    with pytest.raises(AppError) as e:
        await clients.transactions.get_transaction(AS, U1)
    assert (e.value.status, e.value.code, e.value.message) == (400, 'bad_request', 'transactions answered 400')
    clients, _ = make(httpx.Response(500, text='<html>'), retries=0)
    with pytest.raises(AppError) as e:
        await clients.transactions.get_transaction(AS, U1)
    assert (e.value.status, e.value.code, e.value.message) == (500, 'upstream_failed', 'transactions answered 500')


async def test_validation_error_from_the_callee_keeps_its_details() -> None:
    body_ = {'error': {'code': 'validation_failed', 'message': 'Some fields are not valid', 'details': {'tag': 'x'}}}
    clients, _ = make((400, body_))
    with pytest.raises(AppError) as e:
        await clients.transactions.resolve_category(AS, 'x')
    assert (e.value.status, e.value.code, e.value.details) == (400, 'validation_failed', {'tag': 'x'})


# shape check
async def test_answer_of_the_wrong_shape_is_502_upstream_failed() -> None:
    clients, rec = make({'unexpected': True})
    with pytest.raises(AppError) as e:
        await clients.recurring.list(AS)
    assert (e.value.status, e.value.code, e.value.message) == (502, 'upstream_failed', 'recurring answered with an unexpected shape')
    assert e.value.details == {'service': 'recurring'}
    assert len(rec.requests) == 3  # a 502 is retryable for GETs
    clients, rec = make({'unexpected': True})
    with pytest.raises(AppError) as e:
        await clients.transactions.resolve_category(AS, 'x')
    assert e.value.status == 502 and len(rec.requests) == 1


async def test_empty_or_non_json_answer_with_a_contract_is_a_shape_error() -> None:
    clients, _ = make(httpx.Response(200), retries=0)
    with pytest.raises(AppError) as e:
        await clients.ingest.unparsed_count(AS)
    assert e.value.status == 502
    clients, _ = make(httpx.Response(200, text='not json'), retries=0)
    with pytest.raises(AppError) as e:
        await clients.ingest.unparsed_count(AS)
    assert e.value.status == 502


async def test_a_wrong_value_inside_the_contract_is_caught_too() -> None:
    clients, _ = make({'transaction': {**TX, 'amountMinor': 0}}, retries=0)
    with pytest.raises(AppError) as e:
        await clients.transactions.get_transaction(AS, U1)
    assert e.value.status == 502


async def test_without_a_model_the_parsed_json_is_returned() -> None:
    clients, _ = make({'a': 1})
    assert await clients.transactions.request(AS, 'GET', '/x') == {'a': 1}
    clients, _ = make(httpx.Response(204))
    assert await clients.transactions.request(AS, 'DELETE', '/x') is None


# timeout, wiring, lifecycle
async def test_a_slow_answer_times_out_as_unreachable() -> None:
    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200, json={'open': 1})

    c = TransactionsClient(ClientOptions('planning', 'http://transactions:3002', SECRET, timeout=0.05, retries=0, transport=httpx.MockTransport(slow)))
    with pytest.raises(AppError) as e:
        await c.settings(AS)
    assert (e.value.status, e.value.message) == (502, 'transactions is not reachable')
    await c.aclose()


def test_default_timeout_is_eight_seconds_and_two_retries() -> None:
    o = ClientOptions('transactions', 'http://x', 's')
    assert (o.timeout, o.retries) == (8.0, 2)


async def test_create_clients_wires_each_service_to_its_url_and_caller() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, verify_internal_token(SECRET, request.headers['x-internal-token']).svc))
        return httpx.Response(200, json={})

    clients = create_clients('reports', ENV, transport=httpx.MockTransport(handler), retries=0)
    for c in (clients.transactions, clients.auth, clients.planning, clients.recurring, clients.ingest, clients.telegram):
        await c.request(AS, 'GET', '/ping')
    assert seen == [(h, 'reports') for h in ('transactions', 'auth', 'planning', 'recurring', 'ingest', 'telegram')]
    await clients.close()


async def test_close_releases_pools_and_context_manager_does() -> None:
    clients, _ = make({'open': 0})
    async with clients as cs:
        await cs.ingest.unparsed_count(AS)
        http = cs.ingest._http
        assert http is not None and not http.is_closed
    assert http.is_closed and clients.ingest._http is None
    await clients.close()  # closing twice is fine


async def test_an_injected_client_is_used_and_left_open() -> None:
    rec = Recorder({'open': 3})
    shared = httpx.AsyncClient(transport=httpx.MockTransport(rec))
    clients = create_clients('transactions', ENV, client=shared)
    assert (await clients.ingest.unparsed_count(AS)).open == 3
    await clients.close()
    assert not shared.is_closed
    await shared.aclose()
