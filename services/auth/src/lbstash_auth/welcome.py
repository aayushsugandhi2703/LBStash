"""The welcome e-mail sent once, to the address a person signed up with."""

import asyncio

from .svc import Svc

SEND_TIMEOUT_SECONDS = 15
SUBJECT = 'Welcome to LBStash'


def welcome_text(name: str | None, app_url: str) -> str:
    greeting = f'Hi {name},' if name else 'Hi,'
    return (
        f'{greeting}\n\n'
        'Thank you for choosing LBStash for your budget. Your account is ready.\n\n'
        'Why LBStash:\n'
        '- Log a payment in a few seconds from Telegram: /350 food when you spend, +1500 salary when money comes in.\n'
        '- Your message is saved, tagged and then deleted from the chat, so nothing lingers there.\n'
        '- Balance, monthly limits, alerts, trends and repeating payments are built from your own tagged payments.\n'
        '- Private by design: your data lives on your own server, with two-step sign-in and passkeys to protect it.\n\n'
        'To get started, finish the security setup and connect Telegram from the Setup guide:\n'
        f'{app_url}\n\n'
        'If you did not create this account, you can ignore this message.\n\n'
        'LBStash\n'
    )


async def send_welcome(svc: Svc, email: str, name: str | None) -> None:
    """Best effort: a mail failure must never undo or fail a sign-up that already committed."""
    text = welcome_text(name, svc.deps.env.PUBLIC_URL)
    try:
        await asyncio.wait_for(svc.mailer.send(email, SUBJECT, text), SEND_TIMEOUT_SECONDS)
    except Exception as e:  # noqa: BLE001
        svc.deps.log.warning('welcome mail not sent', err=type(e).__name__)
