"""Caller ip and a device label for the sessions list."""

import re
from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True, slots=True)
class ClientInfo:
    ip: str | None
    device: str


def _any(pattern: str, ua: str) -> bool:
    return re.search(pattern, ua) is not None


def device_label(ua: str | None) -> str:
    """'Chrome on Mac', never the raw user agent."""
    if not ua:
        return 'Unknown browser'
    if _any(r'Edg(e|A|iOS)?/', ua):
        browser = 'Edge'
    elif _any(r'OPR/|Opera', ua):
        browser = 'Opera'
    elif _any(r'Firefox/|FxiOS/', ua):
        browser = 'Firefox'
    elif _any(r'Chrome/|CriOS/', ua):
        browser = 'Chrome'
    elif _any(r'Safari/', ua):
        browser = 'Safari'
    else:
        browser = None
    if _any('iPhone', ua):
        os = 'iPhone'
    elif _any('iPad', ua):
        os = 'iPad'
    elif _any('Android', ua):
        os = 'Android'
    elif _any('Windows', ua):
        os = 'Windows'
    elif _any(r'Mac OS X|Macintosh', ua):
        os = 'Mac'
    elif _any('CrOS', ua):
        os = 'Chromebook'
    elif _any('Linux', ua):
        os = 'Linux'
    else:
        os = None
    if browser and os:
        return f'{browser} on {os}'
    return browser or os or 'Unknown browser'


def client_info(request: Request) -> ClientInfo:
    """Caller address (uvicorn resolves the gateway's forwarded address) and device label."""
    return ClientInfo(ip=request.client.host if request.client else None, device=device_label(request.headers.get('user-agent')))
