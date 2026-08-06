"""Applies (or reverses) a Transaction's effect on the real account balance(s) it touched.

Centralizes the balance-mutation logic shared by every place that creates, edits, or
deletes a Transaction row (api/v1/income.py's `log_income`, api/v1/transactions.py's
`update_transaction`/`delete_transaction`, and `record_contribution` in
api/v1/retirement_accounts.py and api/v1/education_accounts.py) so the same three-way
switch on account_type isn't duplicated across four call sites. Every call site follows
the same pattern: `apply_effect(..., amount=X)` to post a transaction, `amount=-X` to fully
reverse one being deleted, or `amount=(new_amount - old_amount)` to apply just the delta
when one is edited - see models/transactions.py's docstring for the broader design.

Employer match on a 401(k)/Roth 401(k) contribution (see
retirement_accounts.record_contribution) is deliberately NOT part of a Transaction's
reversible `amount`: it's a derived, informational figure recomputed from the *employee*
contribution at the moment it's recorded, not something the user themselves logged. Only
the employee's own contribution is ever reversed/adjusted here; a match applied when a
contribution was first recorded stays on the account's balance even if that contribution's
Transaction is later edited or deleted. This is a deliberate v1 simplification, not an
oversight - correctly recomputing and un-applying a historical match would require
re-deriving what the match *would have been* at edit/delete time, which needs the
account's full contribution history, not just this one row.
"""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bank_accounts import BankAccount
from app.models.retirement_accounts import RetirementAccount
from app.models.education_accounts import EducationAccount
from app.models.enums import AllocationDestinationType, TransactionType


async def apply_effect(
    db: AsyncSession,
    *,
    account_type: AllocationDestinationType | None,
    account_id: str | None,
    transaction_type: TransactionType,
    source_bank_account_id: str | None,
    amount: Decimal,
) -> None:
    """Bump (amount > 0) or unwind (amount < 0) a transaction's effect on every account it
    touched. A target row that's since been deleted (see
    models/enums.py:AllocationDestinationType's docstring on why these aren't real
    foreign keys) is silently skipped rather than raising, since the Transaction row
    itself must stay editable/deletable even after the account it once pointed at is
    gone. Caller is responsible for `await db.commit()`.
    """
    if account_type is not None and account_id is not None:
        if account_type == AllocationDestinationType.BANK_ACCOUNT:
            account = await db.get(BankAccount, account_id)
            if account is not None:
                account.current_balance += amount
        elif account_type == AllocationDestinationType.RETIREMENT_ACCOUNT:
            account = await db.get(RetirementAccount, account_id)
            if account is not None:
                account.balance += amount
                if transaction_type == TransactionType.RETIREMENT_CONTRIBUTION:
                    account.contribution_ytd += amount
        elif account_type == AllocationDestinationType.EDUCATION_ACCOUNT:
            account = await db.get(EducationAccount, account_id)
            if account is not None:
                account.balance += amount
                if transaction_type == TransactionType.EDUCATION_CONTRIBUTION:
                    account.contribution_ytd += amount

    if source_bank_account_id is not None:
        source = await db.get(BankAccount, source_bank_account_id)
        if source is not None:
            # Money left the source account - opposite sign from the destination bump.
            source.current_balance -= amount
