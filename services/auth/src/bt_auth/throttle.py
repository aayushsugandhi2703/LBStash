"""Progressive lockout in the database. After `threshold` failures within `decay_minutes` a key locks for `base_seconds`, doubling up to `max_seconds`. Keys are hashes; no e-mail or ip is stored."""

from dataclasses import dataclass

from bt.common import AppError
from bt.crypto import sha256_hex
from bt.db import Tx


@dataclass(frozen=True, slots=True)
class ThrottlePolicy:
    threshold: int
    base_seconds: int
    max_seconds: int
    decay_minutes: int


# Password step, per e-mail + ip.
LOGIN_POLICY = ThrottlePolicy(threshold=5, base_seconds=30, max_seconds=900, decay_minutes=15)
# Password step, per e-mail from any ip.
LOGIN_EMAIL_POLICY = ThrottlePolicy(threshold=15, base_seconds=60, max_seconds=1800, decay_minutes=60)
# Second step and every fresh-code check, per user.
SECOND_STEP_POLICY = ThrottlePolicy(threshold=3, base_seconds=60, max_seconds=900, decay_minutes=15)
# Current-password check on password change.
PASSWORD_CHECK_POLICY = ThrottlePolicy(threshold=5, base_seconds=30, max_seconds=900, decay_minutes=15)


def throttle_key(*parts: str | None) -> str:
    return sha256_hex('|'.join(p or '' for p in parts))


async def locked_for(tx: Tx, key: str) -> int:
    """Seconds the key is still locked, 0 when free."""
    r = await tx.maybe_one(
        'SELECT ceil(extract(epoch FROM locked_until - now()))::int AS s FROM login_throttle '
        'WHERE key_hash = $1 AND locked_until > now()',
        [key],
    )
    return int(r['s']) if r else 0


@dataclass(frozen=True, slots=True)
class FailureResult:
    failures: int
    locked_seconds: int
    attempts_left: int


async def record_failure(tx: Tx, key: str, p: ThrottlePolicy) -> FailureResult:
    r = await tx.one(
        """INSERT INTO login_throttle (key_hash, failures, last_failure_at) VALUES ($1, 1, now())
           ON CONFLICT (key_hash) DO UPDATE SET
             failures = CASE WHEN login_throttle.last_failure_at < now() - make_interval(mins => $2) THEN 1
                             ELSE login_throttle.failures + 1 END,
             last_failure_at = now()
           RETURNING failures""",
        [key, p.decay_minutes],
    )
    failures = int(r['failures'])
    locked_seconds = 0
    if failures >= p.threshold:
        locked_seconds = min(p.max_seconds, p.base_seconds * 2 ** (failures - p.threshold))
        await tx.execute('UPDATE login_throttle SET locked_until = now() + make_interval(secs => $2) WHERE key_hash = $1', [key, locked_seconds])
    return FailureResult(failures, locked_seconds, max(0, p.threshold - failures))


async def clear_failures(tx: Tx, *keys: str) -> None:
    await tx.execute('DELETE FROM login_throttle WHERE key_hash = ANY($1::text[])', [list(keys)])


def locked_error(seconds: int) -> AppError:
    if seconds <= 60:
        msg = 'Too many tries. Wait a minute, then try again.'
    else:
        msg = f'Too many tries. Try again in {-(-seconds // 60)} minutes.'
    return AppError('locked', msg, {'retryAfterSeconds': seconds})
