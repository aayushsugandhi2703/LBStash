"""Boot the telegram service: `python -m bt_telegram.main`."""

from pathlib import Path

from bt.kit import run_service

from .env import Env
from .routes import register
from .workers import start_workers


def main() -> None:
    run_service(
        'telegram',
        register=register,
        env_model=Env,
        migrations_dir=Path(__file__).resolve().parents[2] / 'migrations',
        workers=start_workers,
    )


if __name__ == '__main__':
    main()
