import re
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest
from bt_ingest.parser import (
    TEMPLATES,
    TEMPLATES_VERSION,
    Ignored,
    Parsed,
    ParseInput,
    Unreadable,
    dedupe_key,
    is_otp_like,
    mask_message,
    parse_message,
)
from parser_table import RECEIVED_AT, TABLE, TZ

_AT = datetime(2026, 10, 18, 13, 12, 7, tzinfo=UTC)


def parse(text: str, received_at: str = RECEIVED_AT):
    return parse_message(ParseInput(text=text, received_at=datetime.fromisoformat(received_at), tz=TZ))


class TestParserTable:
    def test_has_at_least_40_rows(self):
        assert len(TABLE) >= 40

    @pytest.mark.parametrize('row', TABLE, ids=[r.name for r in TABLE])
    def test_row(self, row):
        received_at = row.received_at or RECEIVED_AT
        r = parse(row.text, received_at)
        if row.ignored:
            assert r == Ignored(row.ignored)
        elif row.unreadable:
            assert isinstance(r, Unreadable)
            assert r.reason == row.unreadable
            if row.hints:
                assert {k: getattr(r.hints, k) for k in row.hints} == row.hints
        else:
            assert isinstance(r, Parsed)
            e = row.expect
            assert {
                'type': r.tx.type, 'amount_minor': r.tx.amount_minor, 'payee': r.tx.payee, 'reference': r.tx.reference,
                'account_last4': r.tx.account_last4, 'balance_after_minor': r.tx.balance_after_minor, 'reversal': r.tx.reversal,
                'weak_parse': r.tx.weak_parse, 'occurred_at': r.tx.occurred_at,
            } == {
                'type': e.type, 'amount_minor': e.amount_minor, 'payee': e.payee, 'reference': e.reference,
                'account_last4': e.account_last4, 'balance_after_minor': e.balance_after_minor, 'reversal': e.reversal,
                'weak_parse': e.weak_parse, 'occurred_at': e.at or datetime.fromisoformat(received_at),
            }  # fmt: skip
            if e.template is not ...:
                assert r.tx.template == e.template
            assert isinstance(r.tx.amount_minor, int)

    def test_every_otp_row_is_also_recognised_by_is_otp_like_so_it_is_never_stored(self):
        for row in TABLE:
            if row.ignored == 'otp_or_promo' and re.search(r'otp|one time|verification|login code', row.text, re.IGNORECASE):
                assert is_otp_like(row.text), row.name


class TestDedupeKey:
    base: ClassVar[dict] = {'type': 'debit', 'amount_minor': 45000, 'payee': 'RAMESH', 'occurred_at': _AT, 'time_from_message': True, 'reversal': False}

    def test_uses_the_reference_when_there_is_one_and_a_different_key_for_its_reversal(self):
        assert dedupe_key(**{**self.base, 'reference': '123456789012'}) == 'ref:123456789012'
        assert dedupe_key(**{**self.base, 'reference': '123456789012', 'reversal': True}) == 'ref:123456789012:rev'

    def test_hashes_amount_payee_time_bucket_and_source_when_there_is_none(self):
        b = {**self.base, 'reference': None}
        k = dedupe_key(**b)
        assert re.fullmatch(r'h:[0-9a-f]{40}', k)
        assert dedupe_key(**{**b, 'occurred_at': _AT + timedelta(seconds=30)}) == k  # same 5-minute bucket
        assert dedupe_key(**{**b, 'occurred_at': _AT + timedelta(minutes=20)}) != k
        assert dedupe_key(**{**b, 'payee': 'OTHER'}) != k
        assert dedupe_key(**{**b, 'amount_minor': 45001}) != k
        assert dedupe_key(**{**b, 'source': 'recurring'}) != k

    def test_hash_input_format_is_stable(self):
        # sha256("debit|45000|ramesh|<ms // 300000>|captured|"), first 40 hex digits: keys already stored must still match
        from bt.crypto import sha256_hex

        bucket = int(_AT.timestamp() * 1000) // 300_000
        expected = 'h:' + sha256_hex(f'debit|45000|ramesh|{bucket}|captured|')[:40]
        assert dedupe_key(**{**self.base, 'reference': None}) == expected

    def test_the_same_message_sent_twice_gets_the_same_key(self):
        t = 'Rs.99.00 debited from a/c XX1234 on 18-10-26 18:42:07 to VPA cafe@ybl'
        a = parse(t)
        b = parse(t, '2026-10-18T18:43:30+05:30')
        assert isinstance(a, Parsed) and isinstance(b, Parsed) and a.tx.dedupe_key == b.tx.dedupe_key


class TestTemplatesAreData:
    def test_every_template_compiles_and_has_an_id_a_version_and_at_least_one_field(self):
        assert TEMPLATES_VERSION >= 1
        ids: set[str] = set()
        for t in TEMPLATES:
            assert t.id not in ids
            ids.add(t.id)
            assert t.version >= 1
            re.compile(t.match, re.IGNORECASE)
            assert len(t.fields) > 0
            for src in t.fields.values():
                re.compile(src, re.IGNORECASE)

    def test_a_message_the_template_no_longer_matches_still_yields_amount_and_direction_weak_parse(self):
        r = parse('Dear UPI user A/C X1234 has been debited with 450.0 on date 18Oct26 trfd 2 RAMESH')
        assert isinstance(r, Parsed)
        assert (r.tx.type, r.tx.amount_minor, r.tx.template) == ('debit', 45000, None)


class TestMaskingBeforeAnUnreadableMessageIsStored:
    def test_hides_account_digits_long_numbers_and_the_balance_keeps_the_amount(self):
        m = mask_message('Txn of INR 1,250.00 on card ending 4821 at AMAZON, ref 123456789012. A/c XX9876. Avl bal INR 37,591.00')
        assert '1,250.00' in m
        assert not re.search(r'4821|123456789012|9876|37,591', m)


class TestPurityAndMoney:
    def test_never_returns_a_float_amount(self):
        for t in ['Rs 1,00,000.99 credited to a/c XX1234', 'INR 0.07 debited', 'Rs.19.9 debited']:
            r = parse(t)
            assert isinstance(r, Parsed) and isinstance(r.tx.amount_minor, int)
        r = parse('Rs.19.9 debited')
        assert isinstance(r, Parsed) and r.tx.amount_minor == 1990


class TestUnicodeHandling:
    """Pins where Python's `re` differs from the ASCII-only behaviour the patterns assume."""

    def test_a_non_breaking_space_reads_like_a_space(self):
        r = parse('Rs.450.00 debited from a/c XX1234 on 18-10-26 to VPA ramesh@okaxis (UPI Ref No 123456789012)')
        assert isinstance(r, Parsed) and r.tx.amount_minor == 45000 and r.tx.payee == 'ramesh@okaxis'

    def test_an_otp_with_non_breaking_spaces_is_still_an_otp(self):
        assert is_otp_like('Do not share this code')

    def test_arabic_indic_digits_are_not_an_amount(self):
        r = parse('Rs ١٢٣ debited from a/c XX1234')
        assert not isinstance(r, Parsed)

    def test_a_year_below_100_in_a_date_is_not_trusted(self):
        r = parse('Rs 200.00 debited on 0026-10-18 to VPA a@ybl')
        assert isinstance(r, Parsed) and r.tx.occurred_at == datetime.fromisoformat(RECEIVED_AT) and not r.tx.time_from_message
