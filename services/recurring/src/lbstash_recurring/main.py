"""Boot the recurring service: `python -m lbstash_recurring.main`."""

from pathlib import Path

from lbstash.kit import run_service

from .routes import register
from .workers import start_workers

if __name__ == '__main__':
    run_service(
        'recurring',
        register=register,
        migrations_dir=Path(__file__).resolve().parents[2] / 'migrations',
        workers=start_workers,
    )
