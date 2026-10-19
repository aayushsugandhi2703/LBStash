"""Every message text. Only `reveal_text`, built after the user taps Reveal, may contain an amount, payee or balance. Dynamic text is HTML-escaped (parse_mode HTML)."""

from datetime import datetime
from typing import Literal

from bt.common import display_tag, format_inr, tz_parts

from .botapi import Keyboard, escape_html
from .store import Direction, PromptRow


def _n(n: int, one: str, many: str) -> str:
    return f'{n} {one if n == 1 else many}'


class T:
    signed_out = 'Signed out. Send /signin.'
    ask_code = 'Send your 6-digit authenticator code.'
    code_format = 'Send the 6-digit code from your authenticator app, or /signin to start again.'
    already_signed_in = 'You are already signed in.'
    signed_out_done = 'Signed out. Payments keep saving and wait until you send /signin.'
    linked = 'Linked. Send /signin to start.'
    already_linked = 'This chat is linked. Send /signin to start.'
    linked_elsewhere = 'This Telegram account is already linked to another account.'
    unlinked = 'Disconnected. This bot will not send or accept anything now.'
    ask_tag = 'Reply with the tag.'
    tag_placeholder = 'food, gym, rent'
    bad_tag = 'A tag can use letters, numbers and simple punctuation, up to 32 characters. Try again.'
    plan_question = "Add to this month's plan?"
    plan_yes = "Added to this month's plan."
    plan_no = 'OK, not added.'
    help = 'Use the buttons on a prompt, or /pending, /signout, /unlink.'
    nothing_pending = 'Nothing needs a tag.'
    last_one = 'That was the last one.'
    later = 'OK, it stays pending.'
    reveal_off = 'Reveal is switched off.'
    gone = 'That payment no longer exists.'
    stale = 'That button is no longer active.'
    failed = 'Could not do that right now. Try again in a moment.'
    try_again = 'Could not check the code right now. Try again in a moment.'
    balance_nudge = 'Time to compare your balance with your bank. Open Check balance in the web app.'
    balance_button = 'Check balance'

    @staticmethod
    def wrong_code(left: int) -> str:
        return f'That code did not work. {_n(left, "try", "tries")} left.'

    @staticmethod
    def paused(mins: int) -> str:
        return f'Too many wrong codes. Sign-in is paused for {_n(mins, "minute", "minutes")}.'

    @staticmethod
    def still_paused(mins: int) -> str:
        return f'Sign-in is paused. Try again in {_n(mins, "minute", "minutes")}.'

    @staticmethod
    def signed_in(held: int, alert_held: bool) -> str:
        waiting = f' {_n(held, "payment", "payments")} waiting.' if held > 0 else ''
        note = '\nA limit alert was held too.' if alert_held else ''
        return f'Signed in.{waiting}{note}'

    @staticmethod
    def already(name: str) -> str:
        return f'Already {display_tag(name)}'

    @staticmethod
    def saved(name: str) -> str:
        return f'Tagged {display_tag(name)}'

    @staticmethod
    def digest(n: int) -> str:
        return f'{n} {"payment still needs" if n == 1 else "payments still need"} a tag'

    @staticmethod
    def unparsed(n: int) -> str:
        return f'{_n(n, "message", "messages")} could not be read. Open Needs a look in the web app.'

    @staticmethod
    def alert(category: str, level: Literal['alert', 'exceeded'], pct: int) -> str:
        name = escape_html(display_tag(category))
        return f'{name} went over its limit ({pct}%)' if level == 'exceeded' else f'{name} reached {pct}%'


_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def when_label(at: datetime, now: datetime, tz: str) -> str:
    """"6:42 pm", or "18 Oct · 6:42 pm" when it is not today in the user's zone."""
    p = tz_parts(at, tz)
    n = tz_parts(now, tz)
    time = f'{p.h % 12 or 12}:{p.mi:02d} {"pm" if p.h >= 12 else "am"}'
    return time if (p.y, p.m, p.d) == (n.y, n.m, n.d) else f'{p.d} {_MONTHS[p.m - 1]} · {time}'


def dir_label(d: Direction | None) -> str:
    return 'Money in' if d == 'credit' else 'Money out'


def header_text(direction: Direction | None, occurred_at: datetime | None, created_at: datetime, now: datetime, tz: str) -> str:
    return f'{dir_label(direction)} · {when_label(occurred_at or created_at, now, tz)}'


def final_text(p: PromptRow) -> str:
    if p.status in ('tagged', 'auto_tagged'):
        name = escape_html(display_tag(p.category_name or ''))
        return f'{dir_label(p.direction)} · auto-tagged {name} ✓' if p.status == 'auto_tagged' else f'{dir_label(p.direction)} · {name} ✓'
    return f'{dir_label(p.direction)} · removed'


def reveal_text(headline: str, amount_minor: int, payee: str | None) -> str:
    """Only after Reveal: the one place an amount and payee appear."""
    return f'{headline}\n{escape_html(format_inr(amount_minor, symbol=True))}{f" · {escape_html(payee)}" if payee else ""}'


def _label(s: str) -> str:
    return f'{s[:23]}…' if len(s) > 24 else s


def cb(token: str, action: str) -> str:
    return f'{token}:{action}'


def tag_keyboard(p: PromptRow, choices: list[dict[str, str]], *, allow_reveal: bool) -> Keyboard:
    buttons = [{'text': _label(display_tag(c['name'])), 'callback_data': cb(p.token, f'c{i}')} for i, c in enumerate(choices)]
    buttons.append({'text': 'transfer', 'callback_data': cb(p.token, 't')})
    rows: Keyboard = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]  # type: ignore[misc]
    tools = [{'text': '＋ New tag', 'callback_data': cb(p.token, 'n')}]
    if allow_reveal:
        tools.append({'text': 'Reveal', 'callback_data': cb(p.token, 'r')})
    tools.append({'text': 'Later', 'callback_data': cb(p.token, 'l')})
    rows.append(tools)  # type: ignore[arg-type]
    if p.nav:
        rows.append([{'text': 'Next ▶', 'callback_data': cb(p.token, 'x')}])
    return rows


def start_keyboard(token: str) -> Keyboard:
    return [[{'text': 'Start', 'callback_data': cb(token, 's')}]]


def plan_keyboard(token: str) -> Keyboard:
    return [[{'text': 'Yes', 'callback_data': cb(token, 'py')}, {'text': 'No', 'callback_data': cb(token, 'pn')}]]


def balance_keyboard(url: str) -> Keyboard:
    return [[{'text': T.balance_button, 'url': url}]]
