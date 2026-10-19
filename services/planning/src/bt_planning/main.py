"""Boot the planning service: `python -m bt_planning.main`."""

from pathlib import Path

from bt.kit import run_service

from .routes import register
from .workers import start_workers


def main() -> None:
    run_service(
        'planning',
        register=register,
        migrations_dir=Path(__file__).resolve().parents[2] / 'migrations',
        workers=start_workers,
    )


if __name__ == '__main__':
    main()
