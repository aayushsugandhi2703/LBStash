from bt.kit import run_service

from .routes import register


def main() -> None:
    run_service('reports', register=register)


if __name__ == '__main__':
    main()
