from pathlib import Path

from bt.kit import run_service

from .env import Env
from .routes import INGEST_BODY_LIMIT, register
from .workers import start_workers


def main() -> None:
    run_service(
        'ingest',
        register=register,
        env_model=Env,
        migrations_dir=Path(__file__).resolve().parents[2] / 'migrations',
        workers=start_workers,
        body_limit=INGEST_BODY_LIMIT,
    )


if __name__ == '__main__':
    main()
