"""`HttpBotApi` against a scripted fake Telegram (an httpx transport): nothing here ever reaches api.telegram.org."""

import json
import re
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from lbstash_telegram.botapi import BotApiError, BotMe, ForceReply, HttpBotApi, escape_html

Script = Callable[[str, int], tuple[int, Any]]


class FakeTelegram:
    def __init__(self) -> None:
        self.seen: list[dict[str, Any]] = []
        self.counts: dict[str, int] = {}
        self.script: Script = lambda method, n: (200, {'ok': True, 'result': True})

    def handle(self, request: httpx.Request) -> httpx.Response:
        m = re.fullmatch(r'/bot([^/]+)/(\w+)', request.url.path)
        assert m, request.url.path
        token, method = m.groups()
        n = self.counts[method] = self.counts.get(method, 0) + 1
        self.seen.append({'method': method, 'token': token, 'body': json.loads(request.content) if request.content else {}})
        status, body = self.script(method, n)
        return httpx.Response(status, json=body)

    def api(self, sleeps: list[float], **extra: Any) -> HttpBotApi:
        async def sleep(seconds: float) -> None:
            sleeps.append(seconds)

        return HttpBotApi('http://telegram.test', transport=httpx.MockTransport(self.handle), sleep=sleep, **extra)

    def by(self, method: str) -> list[dict[str, Any]]:
        return [s for s in self.seen if s['method'] == method]


@pytest.fixture
def tg() -> FakeTelegram:
    return FakeTelegram()


def too_many(retry_after: int, description: str = 'Too Many Requests') -> tuple[int, Any]:
    return 429, {'ok': False, 'error_code': 429, 'description': description, 'parameters': {'retry_after': retry_after}}


async def test_calls_the_documented_methods_with_html_parse_mode_inline_keyboards_and_force_reply(tg: FakeTelegram) -> None:
    def script(m: str, n: int) -> tuple[int, Any]:
        result = {'id': 5, 'username': 'my_bot'} if m == 'getMe' else {'message_id': 77} if m == 'sendMessage' else True
        return 200, {'ok': True, 'result': result}

    tg.script = script
    a = tg.api([])
    assert await a.get_me('T1') == BotMe(5, 'my_bot')
    await a.set_webhook('T1', url='https://x/telegram/webhook/s', secret_token='sec')
    assert await a.send_message('T1', chat_id=9, text='hi', keyboard=[[{'text': 'A', 'callback_data': 'a:1'}]]) == 77
    await a.send_message('T1', chat_id=9, text='reply', force_reply=ForceReply('tag'))
    await a.edit_message_text('T1', chat_id=9, message_id=77, text='done')
    assert await a.delete_message('T1', 9, 77) is True
    await a.answer_callback_query('T1', 'cb1', 'ok')
    assert tg.by('setWebhook')[0]['body'] == {
        'url': 'https://x/telegram/webhook/s', 'secret_token': 'sec', 'allowed_updates': ['message', 'callback_query']
    }
    first = tg.by('sendMessage')[0]['body']
    assert (first['chat_id'], first['text'], first['parse_mode']) == (9, 'hi', 'HTML')
    assert first['reply_markup'] == {'inline_keyboard': [[{'text': 'A', 'callback_data': 'a:1'}]]}
    assert tg.by('sendMessage')[1]['body']['reply_markup'] == {'force_reply': True, 'input_field_placeholder': 'tag'}
    # no keyboard given: buttons removed
    assert tg.by('editMessageText')[0]['body']['reply_markup'] == {'inline_keyboard': []}
    assert all(s['token'] == 'T1' for s in tg.seen)


async def test_waits_out_retry_after_and_retries_in_order(tg: FakeTelegram) -> None:
    tg.script = lambda m, n: (
        too_many(3, 'Too Many Requests: retry after 3') if m == 'sendMessage' and n == 1 else (200, {'ok': True, 'result': {'message_id': 1}})
    )
    sleeps: list[float] = []
    assert await tg.api(sleeps).send_message('T', chat_id=1, text='x') == 1
    assert sleeps == [3]
    assert len(tg.by('sendMessage')) == 2


async def test_a_retry_after_that_is_too_long_or_keeps_coming_is_thrown_with_the_delay_so_the_job_backs_off(tg: FakeTelegram) -> None:
    tg.script = lambda m, n: too_many(120)
    sleeps: list[float] = []
    with pytest.raises(BotApiError) as long:
        await tg.api(sleeps).send_message('T', chat_id=1, text='x')
    assert long.value.kind == 'rate_limited'
    assert long.value.retry_after == 120
    assert sleeps == []

    tg.script = lambda m, n: too_many(1)
    s2: list[float] = []
    with pytest.raises(BotApiError):
        await tg.api(s2, max_retries=2).send_message('T', chat_id=1, text='x')
    assert s2 == [1, 1]


async def test_maps_failures_to_kinds_and_swallows_message_is_not_modified(tg: FakeTelegram) -> None:
    a = tg.api([])

    def fail(status: int, description: str) -> None:
        tg.script = lambda m, n: (status, {'ok': False, 'error_code': status, 'description': description})

    fail(403, 'Forbidden: bot was blocked by the user')
    with pytest.raises(BotApiError) as e:
        await a.send_message('T', chat_id=1, text='x')
    assert e.value.kind == 'blocked'

    fail(401, 'Unauthorized')
    with pytest.raises(BotApiError) as e:
        await a.get_me('T')
    assert e.value.kind == 'unauthorized'

    fail(400, 'Bad Request: message to edit not found')
    with pytest.raises(BotApiError) as e:
        await a.edit_message_text('T', chat_id=1, message_id=1, text='x')
    assert e.value.kind == 'gone'

    fail(400, 'Bad Request: message is not modified: specified new message content and reply markup are exactly the same')
    assert await a.edit_message_text('T', chat_id=1, message_id=1, text='x') is None

    fail(400, "Bad Request: message can't be deleted for everyone")
    assert await a.delete_message('T', 1, 1) is False

    fail(400, 'Bad Request: bad webhook: HTTPS url must be provided for webhook')
    with pytest.raises(BotApiError) as e:
        await a.set_webhook('T', url='http://x', secret_token='s')
    assert e.value.kind == 'invalid'
    assert str(e.value) == 'Bad Request: bad webhook: HTTPS url must be provided for webhook'

    fail(502, 'Bad Gateway')
    with pytest.raises(BotApiError) as e:
        await a.get_me('T')
    assert e.value.kind == 'network'


async def test_never_puts_the_token_in_an_error_even_when_the_server_is_unreachable() -> None:
    async def no_sleep(_: float) -> None:
        return None

    dead = HttpBotApi('http://127.0.0.1:1', sleep=no_sleep)
    try:
        with pytest.raises(BotApiError) as e:
            await dead.get_me('123456:SECRET-TOKEN-VALUE')
    finally:
        await dead.aclose()
    assert e.value.kind == 'network'
    assert 'SECRET-TOKEN-VALUE' not in f'{e.value} {e.value!r}'
    # the original httpx error carries the URL, so it must not ride along as the cause or context
    assert e.value.__cause__ is None
    assert e.value.__suppress_context__


def test_escapes_html_control_characters() -> None:
    assert escape_html('<b>"x" & y</b>') == '&lt;b&gt;"x" &amp; y&lt;/b&gt;'
