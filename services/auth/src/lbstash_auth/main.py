"""Boot the auth service: `python -m lbstash_auth.main`."""

from pathlib import Path

from lbstash.kit import run_service

from .env import Env
from .routes import register
from .workers import start_workers

if __name__ == '__main__':
    run_service(
        'auth',
        register=register,
        env_model=Env,
        migrations_dir=Path(__file__).resolve().parents[2] / 'migrations',
        workers=start_workers,
    )
