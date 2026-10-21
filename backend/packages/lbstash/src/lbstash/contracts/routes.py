"""Public API (README 9) and the service behind each prefix; the gateway builds its proxy table from this. Browser paths sit under `/api`; `/ingest/*` and `/telegram/webhook/*` also work without it."""

from typing import Final

API_PREFIX: Final = '/api'

ROUTE_TABLE: Final[list[tuple[str, str]]] = [
    ('/auth', 'auth'),
    ('/sessions', 'auth'),
    ('/audit', 'auth'),
    ('/account', 'auth'),
    ('/me/email', 'auth'),
    ('/transactions', 'transactions'),
    ('/credits', 'transactions'),
    ('/categories', 'transactions'),
    ('/balance-check', 'transactions'),  # also matches /balance-checks
    ('/ingest', 'ingest'),
    ('/devices', 'ingest'),
    ('/unparsed', 'ingest'),
    ('/plans', 'planning'),
    ('/budgets', 'planning'),
    ('/alerts', 'planning'),
    ('/recurring', 'recurring'),
    ('/dashboard', 'reports'),
    ('/reports', 'reports'),
    ('/telegram', 'telegram'),
]
# Answered by the gateway itself (composed from several services): GET /me, GET|PATCH /settings, GET /health.
# PATCH /me goes to auth.

# Reachable without a browser session (cookie). They still authenticate themselves some other way.
PUBLIC_PATHS: Final[tuple[str, ...]] = (
    '/auth/register',
    '/auth/login',
    '/auth/demo',  # only answers when DEMO_MODE is on, and only ever for the demo user
    '/auth/2fa/verify',
    '/auth/passkey/login/options',
    '/auth/passkey/login/verify',
    '/auth/refresh',
    '/auth/reset/*',
    '/ingest/message',  # ingest-only bearer token + nonce + timestamp
    '/telegram/webhook/*',  # secret in path + secret-token header
)
# Mutating requests on these skip the CSRF check (no cookie session exists yet, or the caller is not a browser).
CSRF_EXEMPT_PATHS: Final[tuple[str, ...]] = PUBLIC_PATHS
