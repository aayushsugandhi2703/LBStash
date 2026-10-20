"""Mail transports: the e-mail change link and the welcome mail."""

from email.message import EmailMessage
from typing import Protocol
from urllib.parse import unquote, urlsplit

import aiosmtplib
from bt.common import Logger, is_prod

from .env import Env


class Mailer(Protocol):
    async def send(self, to: str, subject: str, text: str) -> None: ...


class LogMailer:
    """Dev transport: logs the body (it holds the link), never the recipient. Silent in production."""

    def __init__(self, log: Logger, production: bool) -> None:
        self._log = log
        self._production = production

    async def send(self, to: str, subject: str, text: str) -> None:
        if self._production:
            return
        # `mail_body`: the logger redacts `body` and `text`
        self._log.info('mail (log transport, development only)', subject=subject, mail_body=text)


class SmtpMailer:
    """Sends through `smtp://user:pass@host:port` (`smtps://` for TLS from the first byte)."""

    def __init__(self, smtp_url: str, sender: str) -> None:
        u = urlsplit(smtp_url)
        if u.scheme not in ('smtp', 'smtps') or not u.hostname:
            raise ValueError('SMTP_URL must look like smtp://user:pass@host:587')
        self._tls = u.scheme == 'smtps'
        self._host = u.hostname
        self._port = u.port or (465 if self._tls else 587)
        self._user = unquote(u.username) if u.username else None
        self._password = unquote(u.password) if u.password else None
        self._from = sender

    async def send(self, to: str, subject: str, text: str) -> None:
        msg = EmailMessage()
        msg['From'], msg['To'], msg['Subject'] = self._from, to, subject
        msg.set_content(text)
        # upgrade with STARTTLS whenever the server offers it
        await aiosmtplib.send(
            msg, hostname=self._host, port=self._port, username=self._user, password=self._password,
            use_tls=self._tls, start_tls=None if not self._tls else False,
        )  # fmt: skip


def create_mailer(env: Env, log: Logger) -> Mailer:
    if env.MAIL_TRANSPORT == 'smtp':
        if not env.SMTP_URL:
            raise ValueError('MAIL_TRANSPORT=smtp needs SMTP_URL')
        host = urlsplit(env.PUBLIC_URL).hostname
        return SmtpMailer(env.SMTP_URL, env.MAIL_FROM or f'Ledger <no-reply@{host}>')
    return LogMailer(log, is_prod(env))
