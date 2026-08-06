"""Replace bank_accounts.cd_maturity_date with cd_start_date + cd_term_months.

Revision ID: 005
Revises: 004
Create Date: 2026-08-03

A CD's term was previously stored only as a maturity date, and
services/combined_simulator.py derived the renewal term length by comparing
that maturity date to `created_at` (when the row was inserted into the
database) - wrong whenever `created_at` didn't reflect when the CD's current
term actually began (e.g. entering a CD opened before the user started using
this app, or editing the maturity date later without the renewal term
changing to match). This migration replaces the single `cd_maturity_date`
column with an explicit `cd_start_date` + `cd_term_months` pair, so the term
length used for both the first maturity and every subsequent renewal is
always the same, explicit, user-provided value - maturity date itself is now
computed on the fly (`cd_start_date + cd_term_months` months) rather than
stored. Both new columns are plain types (Date, Integer), so unlike
002/003's enum-column additions there's no Postgres `CREATE TYPE` step
needed here.

No data migration for existing `cd_maturity_date` values: this project has
no production data to preserve (see docs/progress.md), and there is no
correct way to backfill `cd_start_date` for an existing row automatically.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('bank_accounts', 'cd_maturity_date')
    op.add_column('bank_accounts', sa.Column('cd_start_date', sa.Date(), nullable=True))
    op.add_column('bank_accounts', sa.Column('cd_term_months', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('bank_accounts', 'cd_term_months')
    op.drop_column('bank_accounts', 'cd_start_date')
    op.add_column('bank_accounts', sa.Column('cd_maturity_date', sa.Date(), nullable=True))
