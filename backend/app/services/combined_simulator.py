"""Business logic for projecting every one of a user's bank accounts together into one
combined month-by-month balance, including CD maturity behavior (traditional banking
rules): a CD that reaches maturity (its `cd_start_date` + `cd_term_months`) within the
simulation window either rolls into a new CD term of the same length (`cd_auto_renew=True`)
or deposits its matured balance into a savings account for the rest of the window - the
user's own first savings account if they have one, otherwise a virtual one synthesized
purely for this simulation (never persisted to the database).

A CD's term is stored as an explicit `cd_start_date` + `cd_term_months` rather than a
maturity date, precisely so renewals use that same explicit term length - an earlier
version stored only a maturity date and derived the renewal term from `account.created_at`
(when the row was inserted into the database) to that maturity date, which silently
produced the wrong renewal cadence whenever `created_at` didn't reflect when the CD's
current term actually began (backdating a CD that was opened before the user started
using this app, or editing the maturity date after creation).

This composes `BankSimulatorService.generate_projection` per segment rather than
reimplementing its month loop, so the existing, already-tested single-account
simulation path (`POST /bank-accounts/{id}/simulate`) is untouched. Invoked from
`POST /bank-accounts/simulate-combined` in `api/v1/bank_accounts.py`.

Simplification, documented rather than silently assumed: a CD whose maturity date is
already in the past relative to the simulation's start date is treated as maturing
"now" (month 0) rather than modeling however many terms elapsed before today.

Every `AccountSeries` this module returns carries `is_continuation`, true for every CD
renewal segment after the first: its first projection point duplicates the prior
segment's last point (the same money, carried over at the moment of rollover). Both
`_sum_series` (below) and any client that folds multiple series together (e.g. the
frontend's "fold everything past N series into one 'Other' line" chart logic) must skip
that duplicated point per series - `_sum_series` already did; a Recharts-side bug that
didn't (double-counting that one shared month whenever enough CD renewals pushed a
segment into a folded "Other accounts" line, making it read higher than the real Total)
was found and fixed alongside this field's addition. See
frontend/src/components/charts/CombinedGrowthChart.tsx.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from app.models.bank_accounts import BankAccount, RecurringAction
from app.models.enums import AccountType, CompoundingFrequency
from app.services.bank_simulator import BankSimulatorService, ProjectionPoint

# Interest rate assumed for a savings account the simulation has to synthesize because
# the user has none. Deliberately conservative (0%) rather than guessing a market
# rate on the user's behalf - the app has no real-world rate data to base one on.
VIRTUAL_SAVINGS_RATE = Decimal("0")
VIRTUAL_SAVINGS_ACCOUNT_ID = "virtual-savings"
VIRTUAL_SAVINGS_ACCOUNT_NAME = "Savings (auto-created)"


# Duck-typed stand-in for BankAccount carrying only the fields
# BankSimulatorService.generate_projection actually reads (current_balance, principal,
# interest_rate, compounding_frequency). Lets a CD renewal segment or the synthesized
# virtual savings bucket be projected without constructing/persisting a real ORM row.
@dataclass
class _SimAccountStub:
    current_balance: Decimal
    principal: Decimal
    interest_rate: Decimal | None
    compounding_frequency: CompoundingFrequency


# One account's (or CD renewal segment's, or the savings bucket's) projected series.
# is_continuation is true for every CD renewal segment after the first - see this
# module's docstring for why that matters to anything summing series together.
@dataclass
class AccountSeries:
    account_id: str
    account_name: str
    account_type: AccountType
    compounding_frequency: CompoundingFrequency
    is_virtual: bool
    projections: list[ProjectionPoint]
    is_continuation: bool = False


# Internal wrapper marking whether a series' first point duplicates the prior segment's
# last point (true for every CD renewal segment after the first) so total summation
# doesn't double-count that shared boundary month's balance.
@dataclass
class _SeriesEntry:
    series: AccountSeries
    is_continuation: bool


@dataclass
class CombinedProjectionResult:
    accounts: list[AccountSeries]
    total_projections: list[dict]
    final_total_balance: Decimal


class CombinedSimulatorService:
    """Projects every one of a user's accounts together, applying CD maturity rules."""

    def __init__(self, bank_simulator: BankSimulatorService | None = None):
        self.bank_simulator = bank_simulator or BankSimulatorService()

    # Projects every given account together into one combined series, applying CD
    # maturity/rollover rules where they fall inside the simulated window.
    def generate_combined_projection(
        self,
        accounts: list[BankAccount],
        recurring_by_account_id: dict[str, list[RecurringAction]],
        months: int,
        include_recurring: bool = True,
        start_date: date | None = None,
    ) -> CombinedProjectionResult:
        if start_date is None:
            start_date = date.today()

        savings_target = next(
            (a for a in accounts if a.account_type == AccountType.SAVINGS), None
        )

        entries: list[_SeriesEntry] = []
        injections: list[tuple[int, Decimal]] = []

        for account in accounts:
            is_savings_target = savings_target is not None and account.id == savings_target.id
            recurring_actions = (
                recurring_by_account_id.get(account.id, []) if include_recurring else []
            )

            maturity_date = self._cd_maturity_date(account)
            if account.account_type != AccountType.CD or maturity_date is None:
                if is_savings_target:
                    # Deferred: only generated up front if it turns out no CD injects
                    # into it below (see the trailing block after this loop).
                    continue
                points = self.bank_simulator.generate_projection(
                    account=account,
                    months=months,
                    recurring_actions=recurring_actions,
                    start_date=start_date,
                )
                entries.append(
                    _SeriesEntry(
                        AccountSeries(
                            account_id=account.id,
                            account_name=account.account_name,
                            account_type=account.account_type,
                            compounding_frequency=account.compounding_frequency,
                            is_virtual=False,
                            projections=points,
                        ),
                        is_continuation=False,
                    )
                )
                continue

            maturity_month = self._month_offset(start_date, maturity_date)
            if maturity_month > months:
                points = self.bank_simulator.generate_projection(
                    account=account,
                    months=months,
                    recurring_actions=recurring_actions,
                    start_date=start_date,
                )
                entries.append(
                    _SeriesEntry(
                        AccountSeries(
                            account_id=account.id,
                            account_name=account.account_name,
                            account_type=account.account_type,
                            compounding_frequency=account.compounding_frequency,
                            is_virtual=False,
                            projections=points,
                        ),
                        is_continuation=False,
                    )
                )
                continue

            cd_entries, injection = self._project_cd_with_maturity(
                account, recurring_actions, months, start_date, maturity_month
            )
            entries.extend(cd_entries)
            if injection is not None:
                injections.append(injection)

        if injections:
            entries.extend(
                self._project_savings_with_injections(
                    savings_target,
                    injections,
                    months,
                    start_date,
                    recurring_by_account_id,
                    include_recurring,
                )
            )
        elif savings_target is not None:
            # No CD injected into it after all - project it normally like any other account.
            recurring_actions = (
                recurring_by_account_id.get(savings_target.id, []) if include_recurring else []
            )
            points = self.bank_simulator.generate_projection(
                account=savings_target,
                months=months,
                recurring_actions=recurring_actions,
                start_date=start_date,
            )
            entries.append(
                _SeriesEntry(
                    AccountSeries(
                        account_id=savings_target.id,
                        account_name=savings_target.account_name,
                        account_type=AccountType.SAVINGS,
                        compounding_frequency=savings_target.compounding_frequency,
                        is_virtual=False,
                        projections=points,
                    ),
                    is_continuation=False,
                )
            )

        total_projections = self._sum_series(entries, months, start_date)
        final_total = (
            total_projections[-1]["total_balance"] if total_projections else Decimal("0")
        )

        return CombinedProjectionResult(
            accounts=[entry.series for entry in entries],
            total_projections=total_projections,
            final_total_balance=final_total,
        )

    # Number of whole simulation months between `start` and `target`, rounded up so a
    # maturity date is never missed. A target before `start` collapses to 0 (see the
    # module docstring's documented simplification for already-matured CDs).
    def _month_offset(self, start: date, target: date) -> int:
        if target <= start:
            return 0
        delta = relativedelta(target, start)
        months = delta.years * 12 + delta.months
        if delta.days > 0:
            months += 1
        return months

    # A CD's maturity date, computed from its explicit start date + term length rather
    # than stored directly - see this module's docstring for why. None if either field
    # is unset (a CD account with no term configured yet, e.g. a partially-filled form).
    def _cd_maturity_date(self, account: BankAccount) -> date | None:
        if not account.cd_start_date or not account.cd_term_months:
            return None
        return account.cd_start_date + relativedelta(months=account.cd_term_months)

    # A CD's term length in whole months, used to compute each subsequent renewal's new
    # maturity date. Only called once `_cd_maturity_date` has already confirmed
    # `cd_term_months` is set, so the fallback here is purely defensive.
    def _cd_term(self, account: BankAccount) -> int:
        return max(account.cd_term_months or 1, 1)

    # Re-index a segment's month field by a global offset so points from later segments
    # land on the correct absolute month of the overall simulation.
    def _remap_months(self, points: list[ProjectionPoint], offset: int) -> list[ProjectionPoint]:
        if offset == 0:
            return points
        return [
            ProjectionPoint(
                month=p.month + offset,
                date=p.date,
                balance=p.balance,
                principal=p.principal,
                interest_earned=p.interest_earned,
                deposits=p.deposits,
                withdrawals=p.withdrawals,
            )
            for p in points
        ]

    # Segments a single CD account across its maturity date(s) within the simulation
    # window. Returns the list of series entries produced (the pre-maturity segment,
    # plus one more per renewal if cd_auto_renew), and - only when the CD does NOT
    # auto-renew - the (month, amount) lump sum that needs to land in a savings account.
    def _project_cd_with_maturity(
        self,
        account: BankAccount,
        recurring_actions: list[RecurringAction],
        months: int,
        start_date: date,
        maturity_month: int,
    ) -> tuple[list[_SeriesEntry], tuple[int, Decimal] | None]:
        term = self._cd_term(account)
        stub = _SimAccountStub(
            current_balance=account.current_balance,
            principal=account.principal,
            interest_rate=account.interest_rate,
            compounding_frequency=account.compounding_frequency,
        )

        segments: list[_SeriesEntry] = []
        seg_start_month = 0
        seg_start_date = start_date
        seg_id = account.id
        seg_name = account.account_name
        this_maturity_month = maturity_month
        renewal_n = 0
        injection: tuple[int, Decimal] | None = None

        while True:
            seg_len = this_maturity_month - seg_start_month
            points = self.bank_simulator.generate_projection(
                account=stub,
                months=seg_len,
                recurring_actions=recurring_actions,
                start_date=seg_start_date,
            )
            remapped = self._remap_months(points, seg_start_month)
            segments.append(
                _SeriesEntry(
                    AccountSeries(
                        account_id=seg_id,
                        account_name=seg_name,
                        account_type=AccountType.CD,
                        compounding_frequency=account.compounding_frequency,
                        is_virtual=False,
                        projections=remapped,
                        is_continuation=(renewal_n > 0),
                    ),
                    is_continuation=(renewal_n > 0),
                )
            )

            maturity_point = remapped[-1]
            if this_maturity_month >= months:
                break

            if account.cd_auto_renew:
                renewal_n += 1
                seg_id = f"{account.id}-renewal-{renewal_n}"
                seg_name = f"{account.account_name} (renewal {renewal_n})"
                stub = _SimAccountStub(
                    current_balance=maturity_point.balance,
                    principal=maturity_point.principal,
                    interest_rate=account.interest_rate,
                    compounding_frequency=account.compounding_frequency,
                )
                seg_start_date = maturity_point.date
                seg_start_month = this_maturity_month
                this_maturity_month = min(this_maturity_month + term, months)
                continue

            injection = (this_maturity_month, maturity_point.balance)
            break

        return segments, injection

    # Builds one continuous series for the savings account (real, or a lazily-created
    # virtual one) that absorbs one or more CD-maturity lump sums, each injected as a
    # one-time balance/principal bump at its maturity month.
    def _project_savings_with_injections(
        self,
        savings_target: BankAccount | None,
        injections: list[tuple[int, Decimal]],
        months: int,
        start_date: date,
        recurring_by_account_id: dict[str, list[RecurringAction]],
        include_recurring: bool,
    ) -> list[_SeriesEntry]:
        injections = sorted(injections, key=lambda item: item[0])

        if savings_target is not None:
            stub = _SimAccountStub(
                current_balance=savings_target.current_balance,
                principal=savings_target.principal,
                interest_rate=savings_target.interest_rate,
                compounding_frequency=savings_target.compounding_frequency,
            )
            recurring_actions = (
                recurring_by_account_id.get(savings_target.id, []) if include_recurring else []
            )
            account_id = savings_target.id
            account_name = savings_target.account_name
            is_virtual = False
        else:
            stub = _SimAccountStub(
                current_balance=Decimal("0"),
                principal=Decimal("0"),
                interest_rate=VIRTUAL_SAVINGS_RATE,
                compounding_frequency=CompoundingFrequency.MONTHLY,
            )
            recurring_actions = []
            account_id = VIRTUAL_SAVINGS_ACCOUNT_ID
            account_name = VIRTUAL_SAVINGS_ACCOUNT_NAME
            is_virtual = True

        all_points: list[ProjectionPoint] = []
        seg_start_month = 0
        seg_start_date = start_date

        def _run_segment(target_month: int) -> None:
            nonlocal stub, seg_start_month, seg_start_date, all_points
            seg_len = target_month - seg_start_month
            points = self.bank_simulator.generate_projection(
                account=stub,
                months=seg_len,
                recurring_actions=recurring_actions,
                start_date=seg_start_date,
            )
            remapped = self._remap_months(points, seg_start_month)
            all_points.extend(remapped[1:] if all_points else remapped)
            last = remapped[-1]
            stub = _SimAccountStub(
                current_balance=last.balance,
                principal=last.principal,
                interest_rate=stub.interest_rate,
                compounding_frequency=stub.compounding_frequency,
            )
            seg_start_date = last.date
            seg_start_month = target_month

        for injection_month, amount in injections:
            if injection_month > seg_start_month:
                _run_segment(injection_month)
            elif not all_points:
                # Injection lands at month 0 (an already-matured CD) - synthesize the
                # starting snapshot rather than running a zero-length segment first.
                all_points.append(
                    ProjectionPoint(
                        month=0,
                        date=seg_start_date,
                        balance=stub.current_balance,
                        principal=stub.principal,
                        interest_earned=Decimal("0"),
                        deposits=Decimal("0"),
                        withdrawals=Decimal("0"),
                    )
                )

            # Bump the running balance/principal but deliberately do NOT rewrite the
            # already-recorded point at `seg_start_month`: the CD's own series still
            # owns that exact month (it holds the funds through maturity), so folding
            # the same amount into savings' point for that month would double-count it
            # in the combined total. The bumped balance instead becomes the starting
            # point of the *next* segment, so the transfer is reflected starting the
            # following month - a one-month lag that's an honest trade-off of
            # projecting on a monthly grid rather than a daily one.
            stub = _SimAccountStub(
                current_balance=stub.current_balance + amount,
                principal=stub.principal + amount,
                interest_rate=stub.interest_rate,
                compounding_frequency=stub.compounding_frequency,
            )

        if seg_start_month < months:
            _run_segment(months)
        elif not all_points:
            all_points.append(
                ProjectionPoint(
                    month=0,
                    date=start_date,
                    balance=stub.current_balance,
                    principal=stub.principal,
                    interest_earned=Decimal("0"),
                    deposits=Decimal("0"),
                    withdrawals=Decimal("0"),
                )
            )

        return [
            _SeriesEntry(
                AccountSeries(
                    account_id=account_id,
                    account_name=account_name,
                    account_type=AccountType.SAVINGS,
                    compounding_frequency=stub.compounding_frequency,
                    is_virtual=is_virtual,
                    projections=all_points,
                ),
                is_continuation=False,
            )
        ]

    # Sums every series' balance at each month into the combined total, skipping a
    # continuation segment's first point since it duplicates the prior segment's last
    # point (the same money, not double-counted).
    def _sum_series(
        self, entries: list[_SeriesEntry], months: int, start_date: date
    ) -> list[dict]:
        totals: dict[int, Decimal] = {m: Decimal("0") for m in range(months + 1)}
        for entry in entries:
            points = entry.series.projections
            start_idx = 1 if entry.is_continuation and points else 0
            for point in points[start_idx:]:
                if point.month in totals:
                    totals[point.month] += point.balance

        return [
            {
                "month": m,
                "date": start_date + relativedelta(months=m),
                "total_balance": totals[m].quantize(Decimal("0.01")),
            }
            for m in range(months + 1)
        ]
