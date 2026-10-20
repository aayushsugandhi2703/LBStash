"""Optional per-user list of addresses allowed to sign in and keep sessions. Empty = no limit."""

import ipaddress
from collections.abc import Sequence

from lbstash.db import Tx

MAX_ENTRIES = 20


def normalize_entry(raw: str) -> str:
    """One address or CIDR range, normalised ('203.0.113.7', '203.0.113.0/24'). ValueError if neither."""
    text = raw.strip()
    if not text:
        raise ValueError('empty')
    net = ipaddress.ip_network(text, strict=False)  # a bare address is a one-address network
    return str(net.network_address) if '/' not in text else str(net)


def _address(ip: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not ip:
        return None
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        return None
    return addr.ipv4_mapped if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped else addr


def allows(entries: Sequence[str], ip: str | None) -> bool:
    """True if the list is empty or has `ip`. With a list, an unknown address is refused."""
    if not entries:
        return True
    addr = _address(ip)
    if addr is None:
        return False
    for e in entries:
        net = ipaddress.ip_network(e, strict=False)
        if net.version == addr.version and addr in net:
            return True
    return False


async def allowed_ips(tx: Tx, user_id: str) -> list[str]:
    row = await tx.maybe_one('SELECT allowed_ips FROM users WHERE id = $1', [user_id])
    return list(row['allowed_ips']) if row else []
