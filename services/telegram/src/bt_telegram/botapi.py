"""The only code that talks to the Telegram Bot API; the rest uses the `BotApi` protocol so tests can inject a fake. The token is in the URL, so errors and logs never include it."""

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, NamedTuple, NotRequired, Protocol, TypedDict

import httpx


class InlineButton(TypedDict):
    text: str
    # Either an opaque callback token or (balance nudge) a link to the web app.
    callback_data: NotRequired[str]
    url: NotRequired[str]


Keyboard = list[list[InlineButton]]


@dataclass(frozen=True, slots=True)
class ForceReply:
    """Opens a reply box."""

    placeholder: str | None = None


# rate_limited: 429, wait `retry_after` s · blocked: 403, bot blocked or chat deleted · gone: message deleted or too old
# to edit · unauthorized: 401, token no longer valid
BotErrorKind = Literal['rate_limited', 'blocked', 'gone', 'unauthorized', 'invalid', 'network']


class BotApiError(Exception):
    def __init__(self, kind: BotErrorKind, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.kind: BotErrorKind = kind
        self.retry_after = retry_after

    @property
    def transient(self) -> bool:
        """Worth retrying later."""
        return self.kind in ('rate_limited', 'network')


class BotMe(NamedTuple):
    id: int
    username: str | None


class BotApi(Protocol):
    async def get_me(self, token: str) -> BotMe: ...

    async def set_webhook(self, token: str, *, url: str, secret_token: str) -> None: ...

    async def delete_webhook(self, token: str) -> None: ...

    async def send_message(
        self, token: str, *, chat_id: int, text: str, keyboard: Keyboard | None = None, force_reply: ForceReply | None = None
    ) -> int:
        """Send HTML text (callers escape dynamic text with `escape_html`); returns the message id."""
        ...

    async def edit_message_text(
        self, token: str, *, chat_id: int, message_id: int, text: str, keyboard: Keyboard | None = None
    ) -> None:
        """Omitting `keyboard` removes the buttons. "message is not modified" counts as success."""
        ...

    async def delete_message(self, token: str, chat_id: int, message_id: int) -> bool:
        """False when Telegram would not delete it (too old, already gone)."""
        ...

    async def answer_callback_query(self, token: str, callback_query_id: str, text: str | None = None) -> None: ...


def escape_html(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


_GONE = re.compile(
    r"message to (edit|delete) not found|message can't be (edited|deleted)|message_id_invalid|message identifier is not specified",
    re.IGNORECASE,
)
_NOT_MODIFIED = re.compile(r'message is not modified', re.IGNORECASE)
# A longer `retry_after` is raised so the job backs off instead of waiting inline.
_MAX_INLINE_WAIT_SEC = 30


class HttpBotApi:
    """Bot API over httpx. `transport` and `sleep` are injectable for tests."""

    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        # Inline waits on a 429 before giving up (the job retries later).
        max_retries: int = 3,
    ) -> None:
        self._base = base_url.rstrip('/')
        self._transport = transport
        self._sleep = sleep
        self._max_retries = max_retries
        self._http: httpx.AsyncClient | None = None

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(transport=self._transport, timeout=15.0)
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _call(self, token: str, method: str, body: dict[str, Any]) -> Any:
        attempt = 0
        while True:
            try:
                res = await self._client().post(f'{self._base}/bot{token}/{method}', json=body)
            except (httpx.HTTPError, httpx.InvalidURL, OSError):
                # `from None`: the original error may carry the URL (and so the token)
                raise BotApiError('network', f'telegram {method}: not reachable') from None
            try:
                data = res.json()
            except ValueError:
                data = None
            data = data if isinstance(data, dict) else {}
            if res.is_success and data.get('ok'):
                return data.get('result')

            code = data.get('error_code') or res.status_code
            description = data.get('description') or ''
            if code == 429:
                retry_after = max(1, (data.get('parameters') or {}).get('retry_after') or 1)
                if attempt < self._max_retries and retry_after <= _MAX_INLINE_WAIT_SEC:
                    attempt += 1
                    await self._sleep(retry_after)
                    continue
                raise BotApiError('rate_limited', f'telegram {method}: rate limited', retry_after)
            if code == 401:
                raise BotApiError('unauthorized', f'telegram {method}: token rejected')
            if code == 403:
                raise BotApiError('blocked', f'telegram {method}: forbidden')
            if code == 400 and _NOT_MODIFIED.search(description):
                return None
            if code == 400 and _GONE.search(description):
                raise BotApiError('gone', f'telegram {method}: message gone')
            if code >= 500:
                raise BotApiError('network', f'telegram {method}: server error {code}')
            # Telegram's description never contains the token
            raise BotApiError('invalid', description or f'telegram {method}: refused')

    async def get_me(self, token: str) -> BotMe:
        r = await self._call(token, 'getMe', {})
        return BotMe(r['id'], r.get('username'))

    async def set_webhook(self, token: str, *, url: str, secret_token: str) -> None:
        await self._call(
            token, 'setWebhook', {'url': url, 'secret_token': secret_token, 'allowed_updates': ['message', 'callback_query']}
        )

    async def delete_webhook(self, token: str) -> None:
        await self._call(token, 'deleteWebhook', {})

    async def send_message(
        self, token: str, *, chat_id: int, text: str, keyboard: Keyboard | None = None, force_reply: ForceReply | None = None
    ) -> int:
        body: dict[str, Any] = {
            'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML', 'link_preview_options': {'is_disabled': True},
        }  # fmt: skip
        if force_reply is not None:
            markup: dict[str, Any] = {'force_reply': True}
            if force_reply.placeholder is not None:
                markup['input_field_placeholder'] = force_reply.placeholder
            body['reply_markup'] = markup
        elif keyboard is not None:
            body['reply_markup'] = {'inline_keyboard': keyboard}
        r = await self._call(token, 'sendMessage', body)
        return r['message_id']

    async def edit_message_text(
        self, token: str, *, chat_id: int, message_id: int, text: str, keyboard: Keyboard | None = None
    ) -> None:
        await self._call(
            token,
            'editMessageText',
            {
                'chat_id': chat_id, 'message_id': message_id, 'text': text, 'parse_mode': 'HTML',
                'link_preview_options': {'is_disabled': True}, 'reply_markup': {'inline_keyboard': keyboard or []},
            },
        )  # fmt: skip

    async def delete_message(self, token: str, chat_id: int, message_id: int) -> bool:
        try:
            await self._call(token, 'deleteMessage', {'chat_id': chat_id, 'message_id': message_id})
            return True
        except BotApiError as e:
            if e.kind in ('gone', 'invalid', 'blocked'):
                return False
            raise

    async def answer_callback_query(self, token: str, callback_query_id: str, text: str | None = None) -> None:
        await self._call(token, 'answerCallbackQuery', {'callback_query_id': callback_query_id, **({'text': text} if text else {})})
