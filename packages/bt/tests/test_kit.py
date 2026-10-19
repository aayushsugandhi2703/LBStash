import asyncio
import json
import os
import signal
import socket
import sys
import uuid
from pathlib import Path
from typing import Annotated

import httpx
import pytest
from bt.common import BaseEnv, Errors
from bt.contracts import BudgetEvaluateJob
from bt.crypto import sign_internal_token
from bt.kit import (
    Deps,
    DepsDep,
    IdParam,
    MemoryRateLimiter,
    MonthParam,
    OptionalCtx,
    Paging,
    RequestId,
    ServiceClaims,
    UserCtx,
    boot_service,
    id_param,
    month_param,
)
from bt.kit.testing import TEST_SECRET, build_test_app, headers_for
from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel, Field

MIGRATIONS = str(Path(__file__).parent / 'migrations')
ID = '8f14e45f-ceea-467a-9575-0a3b1f3f0c11'


class Thing(BaseModel):
    n: int = Field(gt=0)
    name: str = 'x'
    nested: dict[str, int] | None = None


def register(app: FastAPI, deps: Deps) -> None:
    r = APIRouter()

    @r.get('/echo/{id}')
    async def echo(p: Annotated[IdParam, Depends(id_param)], ctx: UserCtx):
        return {'id': p.id, 'user': ctx.user_id, 'tz': ctx.tz, 'rid': ctx.request_id}

    @r.post('/things', status_code=201)
    async def things(body: Thing):
        return {'n': body.n}

    @r.get('/boom')
    async def boom(_: ServiceClaims):
        raise Errors.not_found('Thing')

    @r.get('/crash')
    async def crash(_: ServiceClaims):
        raise RuntimeError('secret detail 12345')

    @r.get('/internal/who')
    async def who(claims: ServiceClaims):
        return {'svc': claims.svc}

    @r.get('/plans/{month}')
    async def plan(p: Annotated[MonthParam, Depends(month_param)]):
        return {'month': p.month}

    @r.get('/page')
    async def page(q: Paging):
        return q.model_dump()

    @r.get('/maybe')
    async def maybe(ctx: OptionalCtx, d: DepsDep):
        return {'user': ctx.user_id if ctx else None, 'service': d.env.SERVICE_NAME}

    @r.get('/rid')
    async def rid(request_id_: RequestId, _: ServiceClaims):
        return {'rid': request_id_}

    app.include_router(r)

    @app.get('/own-headers')
    async def own(_: ServiceClaims):
        from fastapi.responses import JSONResponse

        return JSONResponse({}, headers={'X-Frame-Options': 'DENY'})

    @app.get('/note')
    async def note(ctx: UserCtx, d: DepsDep):
        async with d.as_user(ctx) as tx:
            return [x['body'] for x in await tx.many('SELECT body FROM notes')]

    @app.post('/note')
    async def add_note(body: dict, ctx: UserCtx, d: DepsDep):
        async with d.as_user(ctx) as tx:
            await tx.execute('INSERT INTO notes (user_id, body) VALUES ($1, $2)', [ctx.user_id, body['body']])
            await d.bus.enqueue(tx, 'budget.evaluate', BudgetEvaluateJob(
                user_id=ctx.user_id, category_id=ID, period_key='p'))
        return {'ok': True}


@pytest.fixture
async def t():
    h = await build_test_app(service='ledger', register=register)
    yield h
    await h.close()


class TestServiceKitApp:
    async def test_health_needs_no_token_everything_else_does(self, t):
        assert (await t.client.get('/health')).json() == {'ok': True, 'service': 'ledger'}
        assert (await t.client.get('/ready')).status_code == 200
        r = await t.client.get(f'/echo/{ID}')
        assert r.status_code == 401 and r.json() == {'error': {'code': 'unauthorized', 'message': 'Missing service token'}}
        r = await t.client.get(f'/echo/{ID}', headers={'x-internal-token': 'garbage'})
        assert r.status_code == 401 and r.json()['error']['message'] == 'Bad service token'
        expired = sign_internal_token(TEST_SECRET, svc='ledger', user_id='u', ttl_seconds=-5)
        assert (await t.client.get(f'/echo/{ID}', headers={'x-internal-token': expired})).status_code == 401
        other = sign_internal_token('z' * 40, svc='ledger', user_id='u')
        assert (await t.client.get(f'/echo/{ID}', headers={'x-internal-token': other})).status_code == 401

    async def test_unknown_routes_also_need_a_token(self, t):
        assert (await t.client.get('/nothing-here')).status_code == 401

    async def test_carries_the_user_and_zone_from_the_token(self, t):
        u = str(uuid.uuid4())
        r = await t.client.get(f'/echo/{ID}', headers=t.headers_for(u, 'gateway', 'Asia/Kolkata', request_id='req-1'))
        assert r.json() == {'id': ID, 'user': u, 'tz': 'Asia/Kolkata', 'rid': 'req-1'}

    async def test_the_zone_defaults_to_kolkata_when_the_token_has_none(self, t):
        token = sign_internal_token(TEST_SECRET, svc='ledger', user_id='u')
        r = await t.client.get(f'/echo/{ID}', headers={'x-internal-token': token})
        assert r.json()['tz'] == 'Asia/Kolkata'

    async def test_a_route_that_needs_a_user_refuses_a_user_less_token(self, t):
        r = await t.client.get(f'/echo/{ID}', headers=t.headers_for(None, 'ingest'))
        assert r.status_code == 401 and r.json()['error']['code'] == 'unauthorized'
        assert (await t.client.get('/maybe', headers=t.headers_for(None, 'ingest'))).json() == {'user': None, 'service': 'ledger'}

    async def test_validates_body_params_and_query_in_one_error_shape(self, t):
        h = t.headers_for('u-1')
        bad = await t.client.post('/things', headers=h, json={'n': -1, 'nested': {'a': 'x'}})
        assert bad.status_code == 400
        body = bad.json()['error']
        assert body['code'] == 'validation_failed' and body['message'] == 'Some fields are not valid'
        assert set(body['details']) == {'n', 'nested.a'} and all(isinstance(v, str) for v in body['details'].values())
        assert (await t.client.post('/things', headers=h, json={'n': 2})).status_code == 201
        bad_id = await t.client.get('/echo/not-a-uuid', headers=h)
        assert bad_id.status_code == 400 and list(bad_id.json()['error']['details']) == ['id']
        assert list((await t.client.get('/plans/2026-13', headers=h)).json()['error']['details']) == ['month']
        assert (await t.client.get('/plans/2026-10', headers=h)).json() == {'month': '2026-10'}
        r = await t.client.get('/page', headers=h, params={'limit': 500})
        assert list(r.json()['error']['details']) == ['limit']
        assert (await t.client.get('/page', headers=h)).json() == {'cursor': None, 'limit': 20}

    async def test_a_missing_body_is_a_validation_error_not_a_crash(self, t):
        r = await t.client.post('/things', headers=t.headers_for('u'))
        assert r.status_code == 400 and r.json()['error']['code'] == 'validation_failed'

    async def test_bad_json_is_a_bad_request(self, t):
        r = await t.client.post('/things', headers={**t.headers_for('u'), 'content-type': 'application/json'}, content=b'{nope')
        assert r.status_code == 400 and r.json()['error']['code'] == 'bad_request'

    async def test_app_errors_keep_their_status_and_shape(self, t):
        r = await t.client.get('/boom', headers=t.headers_for(None))
        assert r.status_code == 404 and r.json() == {'error': {'code': 'not_found', 'message': 'Thing not found'}}

    async def test_unknown_exceptions_become_500_without_leaking_details(self, t):
        r = await t.client.get('/crash', headers=t.headers_for(None))
        assert r.status_code == 500
        e = r.json()['error']
        assert e['code'] == 'internal' and e['message'] == 'Something went wrong'
        assert e['details'] == {'requestId': r.headers['x-request-id']}
        assert 'secret' not in r.text
        assert r.headers['x-content-type-options'] == 'nosniff'  # error answers get the headers too

    async def test_no_such_route_and_wrong_method_are_404(self, t):
        h = t.headers_for('u')
        for r in (await t.client.get('/nope', headers=h), await t.client.delete('/things', headers=h)):
            assert r.status_code == 404 and r.json() == {'error': {'code': 'not_found', 'message': 'No such route'}}

    async def test_internal_routes_refuse_calls_that_came_through_the_gateway(self, t):
        assert (await t.client.get('/internal/who', headers=t.headers_for('u', 'gateway', 'UTC', True))).status_code == 403
        assert (await t.client.get('/internal/who', headers=t.headers_for(None, 'gateway'))).status_code == 200
        assert (await t.client.get('/internal/who', headers=t.headers_for('u', 'planning'))).json() == {'svc': 'planning'}
        # proxied calls are fine on public routes
        assert (await t.client.get(f'/echo/{ID}', headers=t.headers_for('u', 'gateway', 'UTC', True))).status_code == 200
        r = await t.client.get('/internal/who', headers=t.headers_for('u', 'gateway', 'UTC', True))
        assert r.json() == {'error': {'code': 'forbidden', 'message': 'Internal route'}}

    async def test_the_request_id_comes_from_the_caller_only_when_it_is_safe(self, t):
        h = t.headers_for('u')
        r = await t.client.get('/rid', headers={**h, 'x-request-id': 'abc-123'})
        assert r.json() == {'rid': 'abc-123'} and r.headers['x-request-id'] == 'abc-123'
        for bad in ('has space', 'x' * 200, 'aéb'):
            r = await t.client.get('/rid', headers={**h, 'x-request-id': bad.encode('utf-8')})
            assert r.json()['rid'] != bad and len(r.json()['rid']) == 36
        r = await t.client.get('/rid', headers=h)
        uuid.UUID(r.json()['rid'])

    async def test_security_headers_and_a_routes_own_header_wins(self, t):
        r = await t.client.get('/health')
        assert r.headers['x-content-type-options'] == 'nosniff' and r.headers['referrer-policy'] == 'no-referrer'
        assert r.headers['x-frame-options'] == 'SAMEORIGIN' and 'x-powered-by' not in r.headers
        assert 'content-security-policy' not in r.headers and 'x-request-id' in r.headers
        assert (await t.client.get('/own-headers', headers=t.headers_for(None))).headers['x-frame-options'] == 'DENY'

    async def test_the_body_limit_answers_413(self):
        t = await build_test_app(service='ledger', register=register, body_limit=100)
        try:
            h = {**t.headers_for('u'), 'content-type': 'application/json'}
            big = json.dumps({'n': 1, 'name': 'x' * 500})
            r = await t.client.post('/things', headers=h, content=big)
            assert r.status_code == 413 and r.json()['error']['code'] == 'bad_request'

            async def chunks():  # no content-length: counted while streaming
                for _ in range(10):
                    yield b'{"n": 1, "name": "' + b'y' * 30 + b'"}'

            r = await t.client.post('/things', headers=h, content=chunks())
            assert r.status_code == 413 and r.json()['error']['message'] == 'Request body is too large'
            assert (await t.client.post('/things', headers=h, json={'n': 1})).status_code == 201
        finally:
            await t.close()

    async def test_the_edge_skips_the_token_check_and_never_trusts_a_client_request_id(self):
        def reg(app: FastAPI, deps: Deps) -> None:
            @app.get('/open')
            async def open_(request_id_: RequestId):
                return {'rid': request_id_}

            @app.get('/needs-claims')
            async def needs(_: ServiceClaims):
                return {}

        t = await build_test_app(service='gateway', register=reg, edge=True)
        try:
            r = await t.client.get('/open', headers={'x-request-id': 'client-chosen'})
            assert r.status_code == 200 and r.json()['rid'] != 'client-chosen' and r.headers['x-request-id'] == r.json()['rid']
            assert (await t.client.get('/needs-claims')).status_code == 401
            # an internal path on the edge is just a path: the registrar authenticates
            assert (await t.client.get('/internal/x')).status_code == 404
        finally:
            await t.close()

    async def test_without_a_database_ready_still_answers_and_as_user_explains(self, t):
        assert (await t.client.get('/ready')).json() == {'ok': True, 'service': 'ledger'}
        with pytest.raises(RuntimeError, match='no database'):
            async with t.deps.as_system():
                pass
        with pytest.raises(RuntimeError, match='no message bus'):
            from bt.kit import NoBus

            await NoBus().emit(None, 'x', {})

    async def test_clients_can_be_faked_by_name(self):
        class FakeLedger: ...

        fake = FakeLedger()
        t = await build_test_app(service='planning', register=lambda a, d: None, clients={'ledger': fake})
        try:
            assert t.deps.clients.ledger is fake and t.deps.clients.auth is not fake
        finally:
            await t.close()

    async def test_extra_env_variables_reach_deps(self):
        t = await build_test_app(service='auth', register=lambda a, d: None, env={'ACCESS_TOKEN_SECRET': 'a' * 32})
        try:
            assert t.deps.env.ACCESS_TOKEN_SECRET == 'a' * 32 and t.deps.env.APP_ENV == 'test'
        finally:
            await t.close()


class TestWithDatabase:
    async def test_as_user_applies_rls_and_bus_records_what_the_route_emitted(self, db):
        t = await build_test_app(service='ledger', register=register, pool=db.pool)
        try:
            a, b = str(uuid.uuid4()), str(uuid.uuid4())
            assert (await t.client.post('/note', headers=t.headers_for(a), json={'body': 'mine'})).json() == {'ok': True}
            await t.client.post('/note', headers=t.headers_for(b), json={'body': 'theirs'})
            assert (await t.client.get('/note', headers=t.headers_for(a))).json() == ['mine']
            assert (await t.client.get('/note', headers=t.headers_for(b))).json() == ['theirs']
            assert [j.job for j in t.bus.jobs] == ['budget.evaluate'] * 2
            assert (await t.client.get('/ready')).json() == {'ok': True, 'service': 'ledger'}
        finally:
            await t.close()

    async def test_ready_is_503_when_the_database_is_gone(self, db):
        from bt.db import create_pool

        pool = await create_pool(db.url, name='ready-test', max_size=1)
        t = await build_test_app(service='ledger', register=register, pool=pool)
        try:
            await pool.close()
            r = await t.client.get('/ready')
            assert r.status_code == 503 and r.json() == {'ok': False}
        finally:
            await t.close()

    async def test_boot_service_runs_migrations_starts_the_bus_and_workers_and_closes(self, db):
        started: list[str] = []

        async def workers(deps: Deps) -> None:
            started.append(deps.env.SERVICE_NAME)
            await deps.bus.on_job('budget.evaluate', lambda p: asyncio.sleep(0))

        environ = {
            'INTERNAL_SECRET': TEST_SECRET, 'PORT': '3002', 'DATABASE_URL': db.url, 'QUEUE_DATABASE_URL': db.queue_url,
            'LOG_LEVEL': 'silent', 'NODE_ENV': 'test',
        }  # fmt: skip
        svc = await boot_service('ledger', register=register, migrations_dir=MIGRATIONS, workers=workers, environ=environ)
        try:
            assert started == ['ledger'] and svc.deps.env.APP_ENV == 'test'
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=svc.app), base_url='http://t') as c:
                assert (await c.get('/ready')).status_code == 200
        finally:
            await svc.close()
            await svc.close()  # idempotent

    async def test_a_service_process_serves_and_shuts_down_gracefully_on_sigterm(self, db):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        code = (
            'from fastapi import FastAPI\n'
            'from bt.kit import run_service\n'
            'def register(app, deps):\n'
            '    @app.get("/hi")\n'
            '    async def hi(): return {"hi": 1}\n'
            f'run_service("ledger", register=register, migrations_dir={MIGRATIONS!r})\n'
        )
        env = {
            **os.environ, 'INTERNAL_SECRET': TEST_SECRET, 'PORT': str(port), 'HOST': '127.0.0.1', 'DATABASE_URL': db.url,
            'QUEUE_DATABASE_URL': db.queue_url, 'LOG_LEVEL': 'info', 'APP_ENV': 'test',
        }  # fmt: skip
        proc = await asyncio.create_subprocess_exec(
            sys.executable, '-c', code, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        try:
            async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}') as c:
                for _ in range(100):
                    try:
                        r = await c.get('/hi', headers=headers_for(None))
                        break
                    except httpx.TransportError:
                        await asyncio.sleep(0.1)
                else:
                    raise AssertionError('service did not start')
            assert r.json() == {'hi': 1}
            proc.send_signal(signal.SIGTERM)
            out, _ = await asyncio.wait_for(proc.communicate(), 20)
        finally:
            if proc.returncode is None:
                proc.kill()
        lines = [json.loads(x) for x in out.decode().splitlines() if x.startswith('{')]
        msgs = [x['msg'] for x in lines]
        assert 'listening' in msgs and 'shutting down' in msgs and 'req' in msgs
        assert all('INTERNAL' not in x['msg'] for x in lines)


class TestRateLimiter:
    def test_allows_up_to_max_per_window_then_slides(self):
        now = [0.0]
        rl = MemoryRateLimiter(2, 10, lambda: now[0])
        assert rl.allow('a') and rl.allow('a') and not rl.allow('a')
        assert rl.allow('b')
        now[0] = 10.1
        assert rl.allow('a')
        rl.reset('a')
        assert rl.allow('a') and rl.allow('a') and not rl.allow('a')

    def test_a_refused_call_is_not_counted(self):
        now = [0.0]
        rl = MemoryRateLimiter(1, 10, lambda: now[0])
        assert rl.allow('k')
        now[0] = 5
        assert not rl.allow('k')
        now[0] = 10.5  # the first hit has expired; the refused one at t=5 must not extend the window
        assert rl.allow('k')


def test_base_env_is_what_the_kit_expects():
    assert issubclass(BaseEnv, BaseModel)
