"""The demo account's data: six months of believable money, built without a database.

Pure and deterministic: the same `now` gives the same rows (ids are uuid5 of what the row is), so a re-seed replaces rows with
identical ones and open pages keep working. Money is integer paise. The rules follow the services' schemas:

- transactions: `type` carries the direction, `amount_minor > 0`; `source` captured | manual | recurring | unaccounted;
  captured rows have a bank reference, an account tail and a device; manual rows are what Telegram's `/350 food` makes;
  recurring rows carry `rec:<rule>:<due>` and the rule id; a payee seen before is tagged by "memory" (`tag_rules`).
- balance is never stored: opening balance + credits - debits (so the one Unaccounted gap is a real, pending debit).
- plans and limits follow the spending pattern; alerts are what `evaluate` would have raised (80% and 100% of a limit).
"""

import hashlib
import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Kolkata')
DEMO_USER_ID = '5de0b1a5-0000-4000-8000-00000000d3a0'
_NS = uuid.UUID('5de0b1a5-0000-4000-8000-000000000000')
SEED = 2703
HISTORY_MONTHS = 6
OPENING_BALANCE_MINOR = 2_500_000
ACCOUNT_LAST4 = '4321'
PAISE = 100


def uid(*parts: object) -> str:
    """Stable id for a thing: the same description always gives the same uuid."""
    return str(uuid.uuid5(_NS, '|'.join(str(p) for p in parts)))


def key_of(payee: str) -> str:
    """The payee key the app matches on (lbstash.common.payee_key): lower case, single spaces."""
    return ' '.join(payee.strip().lower().split())


@dataclass(frozen=True)
class Merchant:
    payee: str
    category: str
    low: int  # rupees
    high: int
    weight: float
    # a keyword the user's rule matches instead of remembering this payee ("pharmacy" -> health)
    keyword: str | None = None


MERCHANTS: tuple[Merchant, ...] = (
    Merchant('SWIGGY', 'food', 180, 650, 3.0),
    Merchant('ZOMATO', 'food', 200, 700, 2.5),
    Merchant('ZEPTO', 'food', 350, 1400, 2.0),
    Merchant('BLINKIT', 'food', 250, 1100, 1.5),
    Merchant('CHAAYOS', 'food', 120, 380, 1.2),
    Merchant('STARBUCKS COFFEE', 'food', 280, 620, 1.0),
    Merchant('BIGBASKET', 'food', 900, 2800, 0.5),
    Merchant('UBER INDIA', 'transport', 110, 420, 3.0),
    Merchant('OLA CABS', 'transport', 90, 350, 1.5),
    Merchant('RAPIDO', 'transport', 40, 160, 2.0),
    Merchant('METRO RAIL RECHARGE', 'transport', 300, 500, 0.4, keyword='metro'),
    Merchant('AMAZON PAY INDIA', 'shopping', 399, 3500, 3.0),
    Merchant('MYNTRA', 'shopping', 799, 3200, 2.0),
    Merchant('FLIPKART', 'shopping', 499, 4000, 2.0),
    Merchant('DECATHLON', 'shopping', 999, 4500, 0.5),
    Merchant('BOOKMYSHOW', 'fun', 500, 1400, 2.0),
    Merchant('STEAM GAMES', 'fun', 400, 1800, 1.0),
    Merchant('PVR CINEMAS', 'fun', 300, 900, 1.0),
    Merchant('TOIT BREWPUB', 'fun', 900, 2400, 1.0),
    Merchant('APOLLO PHARMACY', 'health', 180, 900, 3.0, keyword='pharmacy'),
    Merchant('1MG', 'health', 250, 1400, 2.0),
    Merchant('PRACTO CONSULT', 'health', 600, 1200, 0.7),
    Merchant('URBAN COMPANY', 'other', 500, 1500, 2.0),
    Merchant('ATM CASH WITHDRAWAL', 'other', 1000, 4000, 1.0),
)

# events per day: (weekday, weekend)
RATES: dict[str, tuple[float, float]] = {
    'food': (1.15, 1.5),
    'transport': (0.65, 0.5),
    'shopping': (0.16, 0.22),
    'fun': (0.07, 0.25),
    'health': (0.07, 0.07),
    'other': (0.14, 0.14),
}
FLEXIBLE = tuple(RATES)

# What a typical hour looks like for each kind of spend (inclusive).
HOURS: dict[str, tuple[int, int]] = {
    'food': (8, 22), 'transport': (7, 21), 'shopping': (10, 23), 'fun': (12, 23), 'health': (9, 20), 'other': (9, 20),
}

# This month runs hot on purpose, so the demo has limits to warn about and a plan that runs short.
HOT_THIS_MONTH: dict[str, float] = {'shopping': 1.35, 'fun': 1.2, 'food': 1.05}
LIMITED = ('shopping', 'fun', 'food')

# rule name, category, rupees, day of month, note, paused
RULES: tuple[tuple[str, str, int, int, str | None, bool], ...] = (
    ('Rent', 'rent', 24_000, 5, 'to landlord', False),
    ('Netflix', 'netflix', 649, 14, None, False),
    ('Gym', 'gym', 1_500, 25, 'annual pass, paid monthly', False),
    ('Internet', 'internet', 1_180, 27, 'broadband', False),
    ('SIP', 'sip', 15_000, 28, 'index fund', False),
    ('Audible', 'audible', 199, 9, 'paused while travelling', True),
)
FIXED_CATEGORIES = tuple(r[1] for r in RULES)
CATEGORY_NAMES = (*FLEXIBLE, *FIXED_CATEGORIES, 'salary', 'freelance', 'refund')

UNKNOWN_PAYEES = ('UPI-RAMESH K', 'PAYTM MERCHANT 8821', 'GPAY NIKHIL S')

UNREADABLE = (
    ('no_amount', 'HDFCBK: Your a/c XX4321 has been credited. Check the app for the amount and balance.', 5),
    ('direction_unclear', 'AMAZON PAY INDIA has sent a UPI mandate request of Rs XX for approval. Open the app to approve.', 2),
)


def ceil_to(n: int, step: int) -> int:
    return int(math.ceil(n / step) * step)


@dataclass
class Dataset:
    now: datetime
    today: date
    months: list[str]
    user: dict[str, Any]
    categories: list[dict[str, Any]] = field(default_factory=list)
    transactions: list[dict[str, Any]] = field(default_factory=list)
    tx_links: list[dict[str, Any]] = field(default_factory=list)
    tag_rules: list[dict[str, Any]] = field(default_factory=list)
    balance_checks: list[dict[str, Any]] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    plans: list[dict[str, Any]] = field(default_factory=list)
    plan_lines: list[dict[str, Any]] = field(default_factory=list)
    budgets: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    rules: list[dict[str, Any]] = field(default_factory=list)
    device: dict[str, Any] = field(default_factory=dict)
    unparsed: list[dict[str, Any]] = field(default_factory=list)

    def balance_at(self, when: datetime) -> int:
        """What the app would derive: opening balance + credits - debits up to `when`."""
        total = self.settings['opening_balance_minor']
        for t in self.transactions:
            if t['occurred_at'] <= when and t['status'] != 'reversed':
                total += t['amount_minor'] if t['type'] == 'credit' else -t['amount_minor']
        return total


def month_key(d: date) -> str:
    return f'{d.year:04d}-{d.month:02d}'


def add_months(first: date, n: int) -> date:
    y, m = divmod(first.year * 12 + first.month - 1 + n, 12)
    return date(y, m + 1, 1)


def month_days(first: date) -> int:
    return (add_months(first, 1) - first).days


def _poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=TZ)


def _reference(rng: random.Random) -> str:
    return ''.join(str(rng.randint(0, 9)) for _ in range(12))


def _tx(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        'payee': None, 'payee_key': None, 'description': None, 'reference': None, 'account_last4': None, 'category_id': None,
        'recurring_id': None, 'match_hint': None, 'device_id': None, 'captured_at': None, 'weak_parse': False,
        'classified_by': None, 'rule_pattern': None, 'linked': False,
    }
    base.update(kw)
    base['id'] = uid('tx', base['dedupe_key'])
    if base['payee']:
        base['payee_key'] = key_of(base['payee'])
    return base


def build(now: datetime) -> Dataset:
    """Everything the demo account holds, for the moment `now`. Nothing is dated after `now`."""
    now = now.astimezone(TZ)
    today = now.date()
    this_first = today.replace(day=1)
    firsts = [add_months(this_first, -i) for i in range(HISTORY_MONTHS - 1, -1, -1)]
    months = [month_key(f) for f in firsts]
    ds = Dataset(now=now, today=today, months=months, user={'id': DEMO_USER_ID})
    cat = {n: uid('cat', n) for n in CATEGORY_NAMES}
    ds.categories = [{'id': cat[n], 'name': n, 'created_at': _at(firsts[0], 9)} for n in CATEGORY_NAMES]
    ds.device = {
        'id': uid('device'), 'name': 'Pixel 8 SMS forwarder', 'token_hash': hashlib.sha256(b'lbstash-demo-device').hexdigest(),
        'token_hint': 'ledg_live_d3m0…0000', 'tz': 'Asia/Kolkata', 'created_at': _at(firsts[0], 9, 30),
        'last_seen_at': now - timedelta(minutes=3), 'last_delay_seconds': 4,
        'last_test_at': now - timedelta(days=20), 'last_test_source': 'device', 'last_test_delay_seconds': 6, 'last_test_amount_minor': 100 * PAISE,
    }
    device_id = ds.device['id']
    txs: list[dict[str, Any]] = []
    seen: set[str] = set()  # merchants already tagged by hand once; after that memory tags them
    uses: dict[str, int] = {}

    def captured(day_dt: datetime, m: Merchant, rupees: int, rng: random.Random, n: int) -> dict[str, Any]:
        ref = _reference(rng)
        first = m.payee not in seen
        seen.add(m.payee)
        by = 'user' if first else ('rule' if m.keyword else 'memory')
        uses[m.payee] = uses.get(m.payee, 0) + (0 if first else 1)
        return _tx(
            type='debit', amount_minor=rupees * PAISE, occurred_at=day_dt, payee=m.payee, reference=ref, account_last4=ACCOUNT_LAST4,
            category_id=cat[m.category], source='captured', status='confirmed', dedupe_key=f'ref:{ref}', device_id=device_id,
            captured_at=day_dt + timedelta(seconds=rng.randint(3, 25)), classified_by=by, rule_pattern=m.keyword if by == 'rule' else None,
        )

    def manual(day_dt: datetime, m: Merchant, rupees: int, rng: random.Random, n: int) -> dict[str, Any]:
        note = rng.choice(NOTES[m.category])
        return _tx(
            type='debit', amount_minor=rupees * PAISE, occurred_at=day_dt, description=note, category_id=cat[m.category],
            source='manual', status='confirmed', dedupe_key=f'manual:{uid("manual", day_dt.isoformat(), n, m.payee)}', classified_by='user',
        )

    # day-to-day spending
    by_cat: dict[str, list[Merchant]] = {c: [m for m in MERCHANTS if m.category == c] for c in FLEXIBLE}
    day = firsts[0]
    while day <= today:
        rng = random.Random(f'{SEED}:{day.isoformat()}')
        month_rng = random.Random(f'{SEED}:{month_key(day)}')
        month_mult = {c: month_rng.uniform(0.85, 1.2) for c in FLEXIBLE}
        hot = day.replace(day=1) == this_first
        weekend = day.weekday() >= 5
        n = 0
        for c in FLEXIBLE:
            lam = RATES[c][1 if weekend else 0] * month_mult[c]
            for _ in range(_poisson(rng, lam)):
                m = rng.choices(by_cat[c], weights=[x.weight for x in by_cat[c]])[0]
                rupees = int(round(rng.triangular(m.low, m.high, m.low + (m.high - m.low) * 0.3)))
                if hot:
                    rupees = int(round(rupees * HOT_THIS_MONTH.get(c, 1.0)))
                lo, hi = HOURS[c]
                at = _at(day, rng.randint(lo, hi), rng.randint(0, 59))
                if at > now:
                    continue
                n += 1
                if m.low == m.high or rng.random() < 0.68:
                    txs.append(captured(at, m, rupees, rng, n))
                else:
                    txs.append(manual(at, m, rupees, rng, n))
        day += timedelta(days=1)

    # income: salary arrives on the 1st (a bank message), a little freelance and a refund now and then
    for i, first in enumerate(firsts):
        rng = random.Random(f'{SEED}:salary:{first}')
        at = _at(first, 10, 15)
        if at > now:
            continue
        ref = 'N' + ''.join(str(rng.randint(0, 9)) for _ in range(15))
        amount = 82_000 if i < 3 else 85_000
        txs.append(_tx(
            type='credit', amount_minor=amount * PAISE, occurred_at=at, payee='ACME TECHNOLOGIES PVT LTD', reference=ref, account_last4=ACCOUNT_LAST4,
            category_id=cat['salary'], source='captured', status='confirmed', dedupe_key=f'ref:{ref.lower()}', device_id=device_id,
            captured_at=at + timedelta(seconds=9), classified_by='memory',
        ))
    extras = [(1, 17, 'freelance', 12_000, 'logo project, client paid'), (4, 9, 'freelance', 8_500, 'landing page fix'), (3, 12, 'refund', 899, 'Myntra refund')]
    for idx, d, name, rupees, note in extras:
        at = _at(firsts[idx].replace(day=d), 14, 20)
        if at <= now:
            txs.append(_tx(
                type='credit', amount_minor=rupees * PAISE, occurred_at=at, description=note, category_id=cat[name], source='manual',
                status='confirmed', dedupe_key=f'manual:{uid("credit", name, at.isoformat())}', classified_by='user',
            ))

    # repeats: a post on every due day that has passed
    for name, cname, rupees, due_day, note, paused in RULES:
        rid = uid('rule', name)
        last: date | None = None
        stop = add_months(this_first, -2) if paused else None  # a paused rule stopped posting when it was paused
        for first in firsts:
            due = first.replace(day=due_day)
            if due > today or (stop and first >= stop):
                continue
            at = _at(due, 9)
            key = f'rec:{rid}:{due.isoformat()}'
            row = _tx(
                type='debit', amount_minor=rupees * PAISE, occurred_at=at, payee=name, category_id=cat[cname], source='recurring',
                status='confirmed', dedupe_key=key, recurring_id=rid, classified_by='recurring',
            )
            if name in ('Rent', 'SIP'):  # the bank message for the same payment was merged into the post
                ref = _reference(random.Random(f'{SEED}:{key}'))
                row.update(linked=True, reference=ref, account_last4=ACCOUNT_LAST4, device_id=device_id, captured_at=at + timedelta(minutes=1))
                ds.tx_links.append({'dedupe_key': f'ref:{ref}', 'transaction_id': row['id']})
            txs.append(row)
            last = due
        nxt = add_months(this_first, 0).replace(day=due_day)
        if nxt <= today:
            nxt = add_months(this_first, 1).replace(day=due_day)
        ds.rules.append({
            'id': rid, 'name': name, 'note': note, 'category_id': cat[cname], 'amount_minor': rupees * PAISE, 'day_of_month': due_day,
            'next_due': nxt, 'last_handled_due': last, 'paused': paused, 'created_at': _at(firsts[0], 9, 45),
        })

    # a few payments from people and shops the app has not met yet: they wait for a tag
    rng = random.Random(f'{SEED}:untagged')
    for i, (payee, rupees) in enumerate(zip(UNKNOWN_PAYEES, (1200, 340, 560), strict=True)):
        at = now - timedelta(hours=7 + i * 19)
        ref = _reference(rng)
        txs.append(_tx(
            type='debit', amount_minor=rupees * PAISE, occurred_at=at, payee=payee, reference=ref, account_last4=ACCOUNT_LAST4,
            source='captured', status='pending', dedupe_key=f'ref:{ref}', device_id=device_id, captured_at=at + timedelta(seconds=12),
        ))

    txs.sort(key=lambda t: (t['occurred_at'], t['dedupe_key']))
    ds.transactions = txs
    ds.settings = {'opening_balance_minor': OPENING_BALANCE_MINOR, 'reconcile_grace_hours': 6}

    # remembered payees and two keyword rules
    for m in MERCHANTS:
        if m.payee in uses or m.payee in seen:
            if m.keyword:
                ds.tag_rules.append({'kind': 'keyword', 'pattern': m.keyword, 'category_id': cat[m.category], 'hits': uses.get(m.payee, 0)})
            else:
                ds.tag_rules.append({'kind': 'payee', 'pattern': key_of(m.payee), 'category_id': cat[m.category], 'hits': uses.get(m.payee, 0)})
    ds.tag_rules.append({'kind': 'payee', 'pattern': 'acme technologies pvt ltd', 'category_id': cat['salary'], 'hits': len(firsts) - 1})
    for r in ds.tag_rules:
        r['id'] = uid('rule-tag', r['kind'], r['pattern'])

    _balance_checks(ds, cat)
    _planning(ds, cat)
    for reason, text, days_ago in UNREADABLE:
        ds.unparsed.append({'id': uid('unparsed', reason), 'reason': reason, 'text': text, 'received_at': now - timedelta(days=days_ago, hours=3)})
    return ds


NOTES: dict[str, tuple[str, ...]] = {
    'food': ('lunch', 'dinner with friends', 'coffee', 'office snacks', 'groceries', 'biryani'),
    'transport': ('cab to office', 'auto', 'ride home', 'airport cab'),
    'shopping': ('shoes', 'a gift', 'phone cover', 'home stuff', 'headphones'),
    'fun': ('movie night', 'game', 'weekend plan', 'drinks'),
    'health': ('medicines', 'checkup', 'vitamins'),
    'other': ('cash', 'laundry', 'repair', 'tip'),
}


def _balance_checks(ds: Dataset, cat: dict[str, str]) -> None:
    """One old check that matched, and one that found a gap now booked as an Unaccounted debit still waiting for a tag."""
    t_ok = ds.now - timedelta(days=20)
    bal_ok = ds.balance_at(t_ok)
    ds.balance_checks.append({
        'id': uid('check', 'ok'), 'bank_balance_minor': bal_ok, 'transactions_balance_minor': bal_ok, 'gap_minor': 0,
        'source': 'manual', 'status': 'resolved', 'checked_at': t_ok, 'as_of': t_ok, 'transaction_id': None,
    })
    t_gap = ds.now - timedelta(days=9)
    before = ds.balance_at(t_gap)
    gap = -850 * PAISE
    cid = uid('check', 'gap')
    entry = _tx(
        type='debit', amount_minor=-gap, occurred_at=t_gap, source='unaccounted', status='pending', dedupe_key=f'unaccounted:{cid}',
    )
    ds.transactions.append(entry)
    ds.transactions.sort(key=lambda t: (t['occurred_at'], t['dedupe_key']))
    ds.balance_checks.append({
        'id': cid, 'bank_balance_minor': before + gap, 'transactions_balance_minor': before, 'gap_minor': gap,
        'source': 'manual', 'status': 'booked', 'checked_at': t_gap, 'as_of': t_gap, 'transaction_id': entry['id'],
    })
    ds.settings['last_balance_at'] = t_gap


def _planning(ds: Dataset, cat: dict[str, str]) -> None:
    spent: dict[str, dict[str, int]] = {m: {} for m in ds.months}
    income: dict[str, int] = {m: 0 for m in ds.months}
    for t in ds.transactions:
        m = month_key(t['occurred_at'].date())
        if t['type'] == 'credit':
            income[m] += t['amount_minor']
        elif t['category_id']:
            name = next(n for n, i in cat.items() if i == t['category_id'])
            spent[m][name] = spent[m].get(name, 0) + t['amount_minor']
    finished = ds.months[:-1]
    this = ds.months[-1]

    def plan_for(month: str, name: str) -> int:
        if name in FIXED_CATEGORIES:
            return next(r['amount_minor'] for r in ds.rules if r['category_id'] == cat[name])
        if month == this:  # a typical month: the average of the last three finished ones
            base = [spent[m].get(name, 0) for m in finished[-3:]]
            return ceil_to(int(sum(base) / max(1, len(base))), 50_000)
        return ceil_to(int(spent[month].get(name, 0) * 1.05), 50_000)

    for month in ds.months[-3:]:
        pid = uid('plan', month)
        lines = [(n, plan_for(month, n)) for n in (*FLEXIBLE, *(n for n in FIXED_CATEGORIES if n != 'audible'))]  # a paused repeat is not planned
        lines = [(n, a) for n, a in lines if a > 0]
        assigned = sum(a for _, a in lines)
        ds.plans.append({'id': pid, 'month': month, 'total_minor': ceil_to(assigned + 150_000, 500_000)})
        for pos, (n, a) in enumerate(lines):
            ds.plan_lines.append({'id': uid('line', month, n), 'plan_id': pid, 'category_id': cat[n], 'allocated_minor': a, 'position': pos})

    plan_this = {n: a for n, a in ((l['category_id'], l['allocated_minor']) for l in ds.plan_lines if l['plan_id'] == uid('plan', this))}
    for n in LIMITED:
        ds.budgets.append({'id': uid('budget', n), 'category_id': cat[n], 'category': n, 'limit_minor': plan_this[cat[n]]})

    # alerts as `evaluate` raises them: once per month and level, when spending first reaches 80% and 100% of the limit
    for b in ds.budgets:
        for month in ds.months[-3:]:
            running = 0
            raised: set[str] = set()
            for t in ds.transactions:
                if t['type'] != 'debit' or t['category_id'] != b['category_id'] or month_key(t['occurred_at'].date()) != month:
                    continue
                running += t['amount_minor']
                for level, pct in (('alert', 80), ('exceeded', 100)):
                    if level not in raised and running * 100 >= b['limit_minor'] * pct:
                        raised.add(level)
                        current = month == this
                        ds.alerts.append({
                            'id': uid('alert', b['id'], month, level), 'budget_id': b['id'], 'period_key': month, 'level': level, 'pct': pct,
                            'category_name': b['category'], 'sent_at': t['occurred_at'],
                            'read_at': None if current else t['occurred_at'] + timedelta(hours=2),
                        })
