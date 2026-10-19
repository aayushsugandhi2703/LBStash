"""Ledger service contracts: transactions, categories, tag rules, balance checks, ledger settings. The ledger is the single writer of money rows."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .base import (
    Bool,
    CoerceInt,
    DateKey,
    Int,
    IsoDateTime,
    Model,
    MonthKey,
    Opt,
    OptNull,
    Paise,
    PositivePaise,
    StringBool,
    TxType,
    Uuid,
    partial,
    refine_fail,
)
from .common import CategoryDto, TransactionDto

Tag = Annotated[str, StringConstraints(min_length=1, max_length=64)]


# internal: ingest
class IngestTransactionReq(Model):
    type: TxType
    amount_minor: PositivePaise
    # Payment time from the message text; falls back to captured_at.
    occurred_at: IsoDateTime
    payee: OptNull[Annotated[str, StringConstraints(max_length=200)]] = None
    reference: OptNull[Annotated[str, StringConstraints(max_length=64)]] = None
    account_last4: OptNull[Annotated[str, StringConstraints(max_length=4)]] = None
    # "Avl Bal" in the message, when present: feeds the balance check, never stored as the balance.
    balance_after_minor: OptNull[Paise] = None
    device_id: Uuid
    captured_at: IsoDateTime
    weak_parse: Bool = False
    # Message was a reversal / refund / failed notice (README 4.7).
    reversal: Bool = False
    # UPI ref if present, else hash(amount, payee, time bucket, source).
    dedupe_key: Annotated[str, StringConstraints(min_length=1, max_length=128)]


IngestOutcome = Literal[
    'created',  # new row (confirmed if payee memory/keyword matched, else pending)
    'duplicate',  # same dedupe key already saved
    'linked_manual',  # same credit already added by hand within +-1 day: linked, not doubled
    'linked_recurring',  # matches an open recurring post within +-2 days: merged
    'replaced_unaccounted',  # a late real message replaced an Unaccounted entry (balance unchanged)
    'reversed_original',  # a reversal marked the original debit `reversed`
    'saved_as_credit',  # reversal/refund with no matching original: saved as a credit to tag #refund
]


class IngestTransactionRes(Model):
    outcome: IngestOutcome
    transaction: TransactionDto | None


class ManualTransactionReq(Model):
    """Ingest (resolving a "Needs a look" message) or any service creating a plain manual row."""

    type: TxType
    amount_minor: PositivePaise
    occurred_at: IsoDateTime
    payee: OptNull[Annotated[str, StringConstraints(max_length=200)]] = None
    description: OptNull[Annotated[str, StringConstraints(max_length=500)]] = None
    # Tag the row at once (the Telegram `/350 misc` command); an unknown tag becomes a new category.
    tag: Opt[Tag] = None


class TransactionRes(Model):
    transaction: TransactionDto


# internal: recurring
class RecurringPostReq(Model):
    rule_id: Uuid
    name: str
    category_id: Uuid
    amount_minor: PositivePaise
    # Local due date in the user's zone; dedupe key is `rec:<ruleId>:<dueDate>`.
    due_date: DateKey
    # Payee/keyword used to find an already-captured debit within +-2 days of the due date.
    match_hint: OptNull[str] = None


class RecurringPostRes(Model):
    outcome: Literal['posted', 'linked', 'already_posted']
    transaction: TransactionDto


# internal + public: tagging
class TagReq(Model):
    """Give `tag` (creates the category if new) or `category_id`. Same rules for web, Telegram and rules."""

    tag: Opt[Tag] = None
    category_id: Opt[Uuid] = None
    via: Literal['telegram', 'web'] = 'web'

    @model_validator(mode='after')
    def _either(self) -> 'TagReq':
        if bool(self.tag) == bool(self.category_id):
            refine_fail('give either tag or categoryId')
        return self


class TagRes(Model):
    transaction: TransactionDto
    # False when it already had that category (first write wins; the caller shows "already tagged").
    changed: Bool
    previous_category_id: Uuid | None
    # Other pending items for the same payee that the payee rule tagged too.
    also_tagged_ids: list[Uuid]
    category_created: Bool


class PendingRes(Model):
    count: Int
    items: list[TransactionDto]


# categories
class CategoriesRes(Model):
    items: list[CategoryDto]


class ResolveCategoryReq(Model):
    tag: Tag


class ResolveCategoryRes(Model):
    category: CategoryDto
    created: Bool


class CategoriesQuery(Model):
    """`GET /internal/categories?sort=usage&limit=6` returns the most used first (Telegram buttons)."""

    sort: Literal['usage', 'name'] = 'name'
    limit: Opt[Annotated[CoerceInt, Field(ge=1, le=200)]] = None
    include_archived: StringBool = False


# aggregates (reports + planning read these; nothing is cached)
class SpendByCategoryItem(Model):
    category_id: Uuid | None
    category_name: str | None
    spent_minor: Paise


class SpendByCategoryRes(Model):
    items: list[SpendByCategoryItem]


class SpendQuery(Model):
    """`from` inclusive, `to` exclusive (ISO instants from month_range()). Debits only; excludes #transfer and reversed."""

    from_: IsoDateTime = Field(alias='from')
    to: IsoDateTime


class MonthSummaryRes(Model):
    month: MonthKey
    carried_over_minor: Paise
    income_minor: Paise
    spent_minor: Paise
    # Balance right now: opening + all credits - all debits (never stored).
    available_minor: Paise
    untagged_count: Int
    unaccounted_count: Int
    last_captured_at: IsoDateTime | None


class MonthItem(Model):
    month: MonthKey
    income_minor: Paise
    spent_minor: Paise
    closing_minor: Paise


class MonthsRes(Model):
    items: list[MonthItem]


class CategoryMonthItem(Model):
    month: MonthKey
    category_id: Uuid | None
    category_name: str | None
    spent_minor: Paise


class CategoryMonthsRes(Model):
    items: list[CategoryMonthItem]


class DailyItem(Model):
    day: DateKey
    spent_minor: Paise


class DailyRes(Model):
    items: list[DailyItem]


class SummaryQuery(Model):
    month: MonthKey


class MonthsQuery(Model):
    end: MonthKey
    count: CoerceInt = Field(default=6, ge=1, le=24)


class DailyQuery(Model):
    month: MonthKey
    # comma separated
    exclude_category_ids: Opt[str] = None


# settings (owned here, composed by the gateway's /settings)
class LedgerSettings(Model):
    opening_balance_minor: Paise
    # Hours the balance check waits before booking an Unaccounted entry (default 6).
    reconcile_grace_hours: Annotated[Int, Field(ge=0, le=72)]


LedgerSettingsPatch = partial(LedgerSettings, 'LedgerSettingsPatch')


# public: Ledger page (additive; README 11, ui-spec 02-ledger)
class LedgerRowDto(TransactionDto):
    """Row of the Ledger list: the transaction plus how it got its category ("matched rule: uber")."""

    classified_by: Literal['memory', 'rule', 'user', 'recurring'] | None
    # The keyword that matched, when classified_by is 'rule'.
    matched_rule: str | None


class LedgerQuery(Model):
    """`cat`: 'all', 'needs-tag' (pending + Unaccounted), 'uncategorised', or a category id/name.
    `src`: 'all', captured, recurring, manual, 'unaccounted', or 'pending' (needs a tag).
    `month` (YYYY-MM, user's zone) limits list and counts; without it, all time.
    """

    cat: Opt[Annotated[str, StringConstraints(max_length=64)]] = None
    # One flat Literal (a union of Literals would put each branch name into the error path).
    src: Literal['all', 'pending', 'unaccounted', 'captured', 'recurring', 'manual'] = 'all'
    month: Opt[MonthKey] = None
    cursor: Opt[str] = None
    limit: CoerceInt = Field(default=8, ge=1, le=100)


class CategoryStatDto(Model):
    """One entry of the category index: entries in scope, and money out / in (excluding #transfer and reversed)."""

    category_id: Uuid
    category_name: str
    archived: Bool
    count: Int
    spent_minor: Paise
    received_minor: Paise


class LedgerCountsDto(Model):
    all: Int
    needs_tag: Int
    unaccounted: Int
    by_category: list[CategoryStatDto]


class LedgerPageDto(Model):
    month: MonthKey | None
    items: list[LedgerRowDto]
    next_cursor: str | None
    # Entries matching every filter ("showing {items} of {matching}").
    matching: Int
    counts: LedgerCountsDto
    # "the ledger says Rs 37,591"
    balance_minor: Paise


class LedgerFigures(Model):
    """Figures the Ledger shows next to a row after a write. Category stats are for the row's month."""

    balance_minor: Paise
    needs_tag_count: Int
    unaccounted_count: Int
    categories: list[CategoryStatDto]


class PatchTransactionReq(Model):
    """`PATCH /transactions/:id`. First write wins: an already categorised row is returned unchanged unless `recategorize`."""

    tag: Opt[Tag] = None
    category_id: Opt[Uuid] = None
    recategorize: Bool = False

    @model_validator(mode='after')
    def _either(self) -> 'PatchTransactionReq':
        if bool(self.tag) == bool(self.category_id):
            refine_fail('give either tag or categoryId')
        return self


class PatchTransactionRes(TagRes):
    figures: LedgerFigures


class SplitPart(Model):
    amount_minor: PositivePaise
    tag: Opt[Tag] = None
    category_id: Opt[Uuid] = None

    @model_validator(mode='after')
    def _not_both(self) -> 'SplitPart':
        if self.tag and self.category_id:
            refine_fail('give either tag or categoryId')
        return self


class SplitReq(Model):
    """`POST /transactions/:id/split` (pending Unaccounted entries). Parts must add up to the amount; a part with no tag or category stays Unaccounted (at most one)."""

    parts: Annotated[list[SplitPart], Field(min_length=2, max_length=20)]


class SplitRes(Model):
    items: list[TransactionDto]
    figures: LedgerFigures


# public: credits
class CreditReq(Model):
    amount_minor: PositivePaise
    # Local day in the user's zone; not in the future.
    date: DateKey
    tag: Tag
    note: OptNull[Annotated[str, StringConstraints(max_length=500)]] = None
    add_to_plan: Bool = True


class CreditRes(Model):
    transaction: TransactionDto
    category_created: Bool
    # Balance after the credit.
    balance_minor: Paise
    # The month's plan total after adding it; None when not added or planning was unreachable (the event catches up).
    plan_total_minor: Paise | None


class CreditsQuery(Model):
    limit: CoerceInt = Field(default=5, ge=1, le=50)


class CreditsRes(Model):
    items: list[TransactionDto]
    balance_minor: Paise


# public: categories
class CategoryUsageDto(CategoryDto):
    count: Int


class CategoriesUsageRes(Model):
    items: list[CategoryUsageDto]


class CreateCategoryReq(Model):
    name: Tag


class PatchCategoryReq(Model):
    name: Opt[Tag] = None
    archived: Opt[Bool] = None

    @model_validator(mode='after')
    def _something(self) -> 'PatchCategoryReq':
        if self.name is None and self.archived is None:
            refine_fail('nothing to change')
        return self


class DeleteCategoryQuery(Model):
    """Delete is blocked while transactions use the category: pass `reassign_to` to move them first (or archive instead)."""

    reassign_to: Opt[Uuid] = None


class DeleteCategoryRes(Model):
    ok: Literal[True]
    reassigned: Int


# public: balance check
BalanceCheckStatus = Literal['open', 'booked', 'resolved', 'ignored']


class BalanceCheckDto(Model):
    id: Uuid
    bank_balance_minor: Paise
    ledger_balance_minor: Paise
    # bank - ledger: negative = the bank is lower (money left that no message explains).
    gap_minor: Paise
    source: Literal['message', 'manual']
    status: BalanceCheckStatus
    checked_at: IsoDateTime
    # The moment the bank balance refers to.
    as_of: IsoDateTime
    # The Unaccounted entry it booked.
    transaction_id: Uuid | None
    # While open: when the Unaccounted entry gets booked unless a message closes the gap first.
    grace_ends_at: IsoDateTime | None


class BalanceCheckReq(Model):
    bank_balance_minor: Paise


class BalanceCheckRes(Model):
    check: BalanceCheckDto
    # True when the gap is under Rs 1 ("matches the ledger").
    matches: Bool
    # Ledger balance right now.
    ledger_balance_minor: Paise
    transaction: TransactionDto | None


class BalanceChecksQuery(Model):
    limit: CoerceInt = Field(default=10, ge=1, le=50)


class BalanceChecksRes(Model):
    items: list[BalanceCheckDto]
