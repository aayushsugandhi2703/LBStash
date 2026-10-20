"""The error type every service raises; the kit turns it into `{"error": {"code", "message", "details"?}}`."""

from typing import Any, Final, Literal, get_args

ErrorCode = Literal[
    'bad_request',
    'validation_failed',
    'unauthorized',
    'forbidden',
    'not_found',
    'conflict',
    'replay',
    'unprocessable',
    'too_many_requests',
    'two_factor_required',
    'two_factor_invalid',
    'locked',
    'upstream_failed',
    'internal',
]

STATUS: Final[dict[str, int]] = {
    'bad_request': 400,
    'validation_failed': 400,
    'unauthorized': 401,
    'two_factor_required': 401,
    'two_factor_invalid': 401,
    'forbidden': 403,
    'not_found': 404,
    'conflict': 409,
    'replay': 409,
    'unprocessable': 422,
    'too_many_requests': 429,
    'locked': 423,
    'upstream_failed': 502,
    'internal': 500,
}
assert set(STATUS) == set(get_args(ErrorCode))


class AppError(Exception):
    """An error the client sees: stable `code`, human `message`, optional `details`."""

    def __init__(self, code: ErrorCode, message: str, details: Any = None, status: int | None = None) -> None:
        super().__init__(message)
        self.code: ErrorCode = code
        self.message = message
        self.status: int = status if status is not None else STATUS[code]
        self.details = details

    def to_json(self) -> dict[str, Any]:
        """Wire body; `details` is omitted when empty."""
        body: dict[str, Any] = {'code': self.code, 'message': self.message}
        if self.details is not None:
            body['details'] = self.details
        return {'error': body}

    def __repr__(self) -> str:
        return f'AppError({self.code!r}, {self.message!r}, status={self.status})'


class Errors:
    """Factories for the standard errors, so wording stays consistent."""

    @staticmethod
    def bad_request(message: str = 'Bad request', details: Any = None) -> AppError:
        return AppError('bad_request', message, details)

    @staticmethod
    def validation(details: Any, message: str = 'Some fields are not valid') -> AppError:
        return AppError('validation_failed', message, details)

    @staticmethod
    def unauthorized(message: str = 'Not signed in') -> AppError:
        return AppError('unauthorized', message)

    @staticmethod
    def forbidden(message: str = 'Not allowed') -> AppError:
        return AppError('forbidden', message)

    @staticmethod
    def not_found(what: str = 'Item') -> AppError:
        return AppError('not_found', f'{what} not found')

    @staticmethod
    def conflict(message: str, details: Any = None) -> AppError:
        return AppError('conflict', message, details)

    @staticmethod
    def replay(message: str = 'Request already used or too old') -> AppError:
        return AppError('replay', message)

    @staticmethod
    def unprocessable(message: str, details: Any = None) -> AppError:
        return AppError('unprocessable', message, details)

    @staticmethod
    def too_many(message: str = 'Too many requests, try again later') -> AppError:
        return AppError('too_many_requests', message)

    @staticmethod
    def two_factor_required() -> AppError:
        return AppError('two_factor_required', 'A code from your authenticator is needed')

    @staticmethod
    def two_factor_invalid() -> AppError:
        return AppError('two_factor_invalid', 'That code did not work')

    @staticmethod
    def locked(message: str = 'Temporarily locked') -> AppError:
        return AppError('locked', message)

    @staticmethod
    def upstream(service: str, message: str = 'A service did not answer') -> AppError:
        return AppError('upstream_failed', message, {'service': service})

    @staticmethod
    def internal(message: str = 'Something went wrong') -> AppError:
        return AppError('internal', message)
