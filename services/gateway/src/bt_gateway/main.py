"""Entry point: `python -m bt_gateway.main`."""

from bt.kit import run_service

from .env import Env
from .routes import register

if __name__ == '__main__':
    run_service('gateway', register=register, env_model=Env, edge=True)
