import asyncio
import uuid

from planning_harness import Harness


def rs(n: int) -> int:
    return n * 100


class TestPlans:
    u = str(uuid.uuid4())

    async def test_an_unplanned_month_reads_as_an_empty_plan(self, h: Harness) -> None:
        r = await h.get(self.u, '/plans/2026-12')
        assert r.status_code == 200
        assert r.json() == {'month': '2026-12', 'totalMinor': 0, 'lines': [], 'assignedMinor': 0, 'unassignedMinor': 0}

    async def test_50000_with_sip_10000_and_rent_20000_leaves_20000_unassigned_spend_filled_from_the_transactions(
        self, h: Harness
    ) -> None:
        u = self.u
        sip, rent = h.transactions.cat('sip'), h.transactions.cat('rent')
        h.transactions.set_spend('2026-11', 'rent', rs(20000))
        put = await h.send(
            u, 'PUT', '/plans/2026-11',
            {'totalMinor': rs(50000), 'lines': [{'categoryId': sip, 'allocatedMinor': rs(10000)}, {'categoryId': rent, 'allocatedMinor': rs(20000)}]},
        )  # fmt: skip
        assert put.status_code == 200
        assert put.json() == {
            'month': '2026-11', 'totalMinor': rs(50000), 'assignedMinor': rs(30000), 'unassignedMinor': rs(20000),
            'lines': [
                {'categoryId': sip, 'categoryName': 'sip', 'allocatedMinor': rs(10000), 'spentMinor': 0},
                {'categoryId': rent, 'categoryName': 'rent', 'allocatedMinor': rs(20000), 'spentMinor': rs(20000)},
            ],
        }  # fmt: skip
        assert (await h.get(u, '/plans/2026-11')).json() == put.json()
        # the spend asked for is the user's calendar month [Nov 1, Dec 1) in Kolkata
        assert h.transactions.last_range == {'from': '2026-10-31T18:30:00.000Z', 'to': '2026-11-30T18:30:00.000Z'}

    async def test_put_replaces_everything_a_new_tag_creates_its_category_through_the_transactions(self, h: Harness) -> None:
        u = self.u
        before = h.transactions.calls['resolve']
        r = await h.send(
            u,
            'PUT',
            '/plans/2026-11',
            {'totalMinor': rs(50000), 'lines': [{'tag': '#Gym', 'allocatedMinor': rs(1500)}]},
        )
        assert r.status_code == 200
        assert h.transactions.calls['resolve'] == before + 1
        body = r.json()
        assert len(body['lines']) == 1
        assert body['lines'][0]['categoryName'] == 'gym'
        assert body['lines'][0]['allocatedMinor'] == rs(1500)
        assert body['unassignedMinor'] == rs(48500)

    async def test_over_assigning_is_allowed_and_shows_as_a_negative_unassigned(self, h: Harness) -> None:
        a = h.transactions.cat('food')
        r = await h.send(
            self.u,
            'PUT',
            '/plans/2026-09',
            {'totalMinor': rs(1000), 'lines': [{'categoryId': a, 'allocatedMinor': rs(1500)}]},
        )
        assert r.status_code == 200
        assert r.json()['assignedMinor'] == rs(1500)
        assert r.json()['unassignedMinor'] == -rs(500)

    async def test_a_zero_allocation_and_an_empty_line_list_are_fine(self, h: Harness) -> None:
        r = await h.send(self.u, 'PUT', '/plans/2026-08', {'totalMinor': 0, 'lines': []})
        body = r.json()
        assert (body['totalMinor'], body['lines'], body['unassignedMinor']) == (0, [], 0)

    async def test_validation_bad_month_negative_amounts_id_and_tag_together_neither_unknown_category_duplicate_category(
        self, h: Harness
    ) -> None:
        u = self.u
        c = h.transactions.cat('food')

        async def put(body: dict) -> int:
            return (await h.send(u, 'PUT', '/plans/2026-10', body)).status_code

        assert (await h.get(u, '/plans/2026-13')).status_code == 400
        assert await put({'totalMinor': -1, 'lines': []}) == 400
        assert await put({'totalMinor': 1.5, 'lines': []}) == 400
        assert await put({'totalMinor': 1, 'lines': [{'categoryId': c, 'allocatedMinor': -5}]}) == 400
        assert await put({'totalMinor': 1, 'lines': [{'categoryId': c, 'tag': 'x', 'allocatedMinor': 5}]}) == 400
        assert await put({'totalMinor': 1, 'lines': [{'allocatedMinor': 5}]}) == 400
        unknown = await h.send(
            u,
            'PUT',
            '/plans/2026-10',
            {'totalMinor': 1, 'lines': [{'categoryId': str(uuid.uuid4()), 'allocatedMinor': 5}]},
        )
        assert unknown.status_code == 400
        assert unknown.json()['error']['code'] == 'validation_failed'
        dup = await h.send(
            u,
            'PUT',
            '/plans/2026-10',
            {'totalMinor': 1, 'lines': [{'categoryId': c, 'allocatedMinor': 5}, {'tag': 'Food', 'allocatedMinor': 5}]},
        )
        assert dup.status_code == 400
        assert dup.json()['error']['details'] == {'lines.1': 'This category is already on the plan'}
        # nothing was saved by the failed calls
        assert (await h.get(u, '/plans/2026-10')).json()['lines'] == []

    async def test_user_b_never_sees_user_as_plan(self, h: Harness) -> None:
        u, b = self.u, str(uuid.uuid4())
        body = (await h.get(b, '/plans/2026-11')).json()
        assert body['totalMinor'] == 0
        assert body['lines'] == []
        await h.send(b, 'PUT', '/plans/2026-11', {'totalMinor': rs(7), 'lines': []})
        assert (await h.get(u, '/plans/2026-11')).json()['totalMinor'] == rs(50000)
        assert (await h.get(b, '/plans/2026-11')).json()['totalMinor'] == rs(7)

    async def test_refuses_a_call_without_a_user(self, h: Harness) -> None:
        r = await h.client.get('/plans/2026-11', headers=h.as_(None, 'transactions'))
        assert r.status_code == 401


class TestCreditToThePlanTotalInternal:
    u = str(uuid.uuid4())

    async def credit(self, h: Harness, tx_id: str, amount: int, month: str = '2026-10'):
        return await h.internal(
            self.u,
            'POST',
            f'/internal/plans/{month}/credit',
            {'transactionId': tx_id, 'amountMinor': amount},
            svc='transactions',
        )

    async def test_adds_to_the_total_creating_the_plan_if_there_is_none_and_is_idempotent_per_transaction_id(
        self, h: Harness
    ) -> None:
        tx1, tx2 = str(uuid.uuid4()), str(uuid.uuid4())
        assert (await self.credit(h, tx1, rs(500))).json() == {'totalMinor': rs(500)}
        assert (await self.credit(h, tx1, rs(500))).json() == {'totalMinor': rs(500)}
        assert (await self.credit(h, tx2, rs(250))).json() == {'totalMinor': rs(750)}

    async def test_the_http_call_and_the_credit_added_event_together_count_once(self, h: Harness) -> None:
        u = self.u
        tx = str(uuid.uuid4())
        await self.credit(h, tx, rs(100), '2026-10')
        await h.bus.emit(
            h.db.pool,
            'credit.added',
            {'userId': u, 'transactionId': tx, 'month': '2026-10', 'amountMinor': rs(100), 'addToPlan': True},
        )
        await h.bus.drain()
        assert (await h.get(u, '/plans/2026-10')).json()['totalMinor'] == rs(850)
        # and the other way round: event first, then HTTP
        tx3 = str(uuid.uuid4())
        await h.bus.emit(
            h.db.pool,
            'credit.added',
            {'userId': u, 'transactionId': tx3, 'month': '2026-10', 'amountMinor': rs(50), 'addToPlan': True},
        )
        await h.bus.drain()
        assert (await self.credit(h, tx3, rs(50))).json()['totalMinor'] == rs(900)

    async def test_add_to_plan_false_leaves_the_plan_alone(self, h: Harness) -> None:
        u = self.u
        await h.bus.emit(
            h.db.pool,
            'credit.added',
            {
                'userId': u,
                'transactionId': str(uuid.uuid4()),
                'month': '2026-10',
                'amountMinor': rs(999),
                'addToPlan': False,
            },
        )
        await h.bus.drain()
        assert (await h.get(u, '/plans/2026-10')).json()['totalMinor'] == rs(900)

    async def test_concurrent_duplicates_still_count_once(self, h: Harness) -> None:
        tx = str(uuid.uuid4())
        await asyncio.gather(*(self.credit(h, tx, rs(10), '2027-01') for _ in range(3)))
        assert (await h.get(self.u, '/plans/2027-01')).json()['totalMinor'] == rs(10)

    async def test_is_internal_only_and_needs_a_user_and_a_positive_amount(self, h: Harness) -> None:
        u = self.u
        body = {'transactionId': str(uuid.uuid4()), 'amountMinor': 5}
        proxied = await h.internal(u, 'POST', '/internal/plans/2026-10/credit', body, proxied=True)
        assert proxied.status_code == 403
        no_user = await h.internal(None, 'POST', '/internal/plans/2026-10/credit', body, svc='transactions')
        assert no_user.status_code == 401
        assert (await self.credit(h, str(uuid.uuid4()), 0)).status_code == 400
        assert (await self.credit(h, 'nope', 5)).status_code == 400
