import pytest
from lbstash_gateway.paths import (
    bucket_of,
    is_csrf_exempt,
    is_public_path,
    normalize_path,
    query_of,
    resolve_service,
)
from lbstash_gateway.session_cache import SessionCache, SessionState


class TestPaths:
    def test_normalises_the_api_prefix_query_and_trailing_slash(self) -> None:
        assert normalize_path('/api/transactions?month=2026-10') == '/transactions'
        assert normalize_path('/transactions/') == '/transactions'
        assert normalize_path('/api') == '/'
        assert normalize_path('/apix/transactions') == '/apix/transactions'
        assert query_of('/a?b=1&c=2') == '?b=1&c=2'
        assert query_of('/a') == ''

    @pytest.mark.parametrize(
        'p', ['/a/../b', '/a/./b', '/a/%2E%2e/b', '/a%2Fb', '/a\\b', '/a//b', '/a%00', '/a%0d%0ax', '/a%1F', '/a%7f', '/a\x7f']
    )
    def test_refuses_anything_that_could_be_normalised_out_of_the_route_table(self, p: str) -> None:
        assert normalize_path(p) is None

    def test_public_and_exempt_paths_follow_the_contract(self) -> None:
        assert is_public_path('/auth/login')
        assert not is_public_path('/auth/login/x')
        assert is_public_path('/auth/reset/confirm')
        assert not is_public_path('/auth/reset')
        assert is_public_path('/telegram/webhook/abc')
        assert not is_public_path('/telegram/pairing')
        assert is_public_path('/ingest/message')
        assert is_csrf_exempt('/auth/refresh')
        assert not is_csrf_exempt('/auth/session')

    def test_longest_prefix_wins_patch_me_is_auth_get_me_is_not_in_the_table(self) -> None:
        assert resolve_service('/me/email', 'POST') == 'auth'
        assert resolve_service('/balance-checks', 'GET') == 'transactions'
        assert resolve_service('/me', 'PATCH') == 'auth'
        assert resolve_service('/me', 'GET') is None
        assert resolve_service('/settings', 'GET') is None
        assert resolve_service('/internal/me', 'GET') is None

    def test_strict_buckets(self) -> None:
        assert bucket_of('/auth/login') == 'login'
        assert bucket_of('/auth/2fa/verify') == '2fa'
        assert bucket_of('/auth/demo') == 'demo'
        assert bucket_of('/auth/reset/request') == 'reset'
        assert bucket_of('/ingest/message') == 'ingest'
        assert bucket_of('/telegram/webhook/x') == 'webhook'
        assert bucket_of('/transactions') is None


class TestSessionCache:
    def test_keeps_a_positive_answer_for_the_ttl_only(self) -> None:
        t = [0.0]
        c = SessionCache(10.0, lambda: t[0])
        assert not c.has('s')
        c.remember('s', True)
        t[0] = 9.999
        assert c.has('s')
        assert c.get('s') == SessionState(limited=True)
        t[0] = 10.0
        assert not c.has('s')
        assert c.get('s') is None
