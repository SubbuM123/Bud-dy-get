"""Shared enumerations for the bank account domain.

These enums are the single source of truth for values that must stay in sync
between the SQLAlchemy models (which enforce them at the database level via
SQL ENUM types) and the Pydantic schemas (which validate them at the API
boundary). Previously these were declared twice - once in models/bank_accounts.py
and once in schemas/bank_accounts.py - which risked the two definitions drifting
apart. Both layers now import from this module instead.
"""

from enum import Enum


# Type of bank account being simulated or tracked.
class AccountType(str, Enum):
    SAVINGS = "savings"
    CHECKING = "checking"
    CD = "cd"


# How often interest compounds on an account balance.
class CompoundingFrequency(str, Enum):
    DAILY = "daily"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


# Direction of a recurring or one-off cash movement on an account.
class ActionType(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"


# Unit used to express how often a recurring action repeats.
class FrequencyUnit(str, Enum):
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"


# Predetermined category tag for a recurring action, used for future spend/income
# analysis by category rather than free-text description alone.
class ActionCategory(str, Enum):
    SALARY = "salary"
    HOUSING = "housing"
    UTILITIES = "utilities"
    INSURANCE = "insurance"
    RETIREMENT = "retirement"
    INVESTMENT = "investment"
    HEALTHCARE = "healthcare"
    ENTERTAINMENT = "entertainment"
    TRANSPORTATION = "transportation"
    OTHER = "other"


# Type of retirement/tax-advantaged account being tracked. SEP_IRA and SIMPLE_IRA are
# modeled as accounts a user can create, but retirement_rules.py only implements limit
# calculations for 401(k)/Roth 401(k), Traditional/Roth IRA, and HSA - the ones actually
# researched and documented in docs/phase4-plan.md.
class RetirementAccountType(str, Enum):
    TRADITIONAL_401K = "traditional_401k"
    ROTH_401K = "roth_401k"
    TRADITIONAL_IRA = "traditional_ira"
    ROTH_IRA = "roth_ira"
    SEP_IRA = "sep_ira"
    SIMPLE_IRA = "simple_ira"
    HSA = "hsa"


# How an employer's matching contributions become the employee's own money over time.
class VestingType(str, Enum):
    IMMEDIATE = "immediate"
    CLIFF = "cliff"
    GRADED = "graded"


# IRS tax filing status, used to look up income phaseout ranges for Roth IRA eligibility
# and Traditional IRA deductibility.
class FilingStatus(str, Enum):
    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_filing_jointly"
    MARRIED_FILING_SEPARATELY = "married_filing_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"


# How often a recurring retirement contribution repeats. Deliberately just these two
# (unlike RecurringAction's days/weeks/months) since real-world retirement contributions
# are set up through payroll (monthly, biweekly-rounds-to-monthly in practice) or as a
# lump sum once a year (e.g. topping off an IRA before the tax deadline) - see
# services/retirement_simulator.py for how a yearly contribution is folded into the
# simulation's monthly grid.
class ContributionFrequency(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


# Type of education-savings account being tracked. COVERDELL_ESA and CUSTODIAL_UTMA_UGMA
# are recorded-but-not-researched placeholders for future extensibility, mirroring how
# RetirementAccountType includes SEP_IRA/SIMPLE_IRA/HSA today - only 529 plan rules are
# actually researched and enforced, in docs/phase4.5-plan.md.
class EducationAccountType(str, Enum):
    FIVE_TWENTY_NINE = "529_plan"
    COVERDELL_ESA = "coverdell_esa"
    CUSTODIAL_UTMA_UGMA = "custodial_utma_ugma"


# Lifecycle state of an uploaded receipt as it moves through OCR/text extraction. Set to
# PENDING when a Receipt row is created (upload endpoint), PROCESSING when the Celery task
# picks it up, then COMPLETED (every core field extracted with high confidence),
# NEEDS_REVIEW (extracted, but at least one core field's confidence is below the review
# threshold - see services/receipt_parser.py), or FAILED (extraction raised or produced no
# usable text at all) once the task finishes. See docs/phase3-plan.md's processing pipeline
# diagram.
class ReceiptProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


# Which extraction path produced a receipt's raw_ocr_text / fields - recorded so a human
# reviewing a low-confidence extraction (or a future reprocessing pass) knows whether
# Tesseract ran on an image, a PDF's embedded text was read directly (most accurate, no
# OCR involved), a scanned/image-only PDF was rasterized and OCR'd as a fallback, or the
# fields were entered by hand with no receipt file at all.
class ExtractionMethod(str, Enum):
    TESSERACT = "tesseract"
    PDF_TEXT = "pdf_text"
    PDF_OCR = "pdf_ocr"
    MANUAL = "manual"


# How often a recurring income (salary, side income) is received. Deliberately mirrors
# real payroll cadences rather than bank_accounts.RecurringAction's generic
# days/weeks/months, since income - unlike a withdrawal a user can schedule however they
# like - actually arrives on one of a small number of real-world payroll schedules.
class IncomeFrequency(str, Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    SEMI_MONTHLY = "semi_monthly"
    MONTHLY = "monthly"


# Which kind of account an IncomeAllocation or Transaction is pointing at. Deliberately a
# plain enum + string id pair rather than three nullable FK columns (one per possible
# target table) or a single polymorphic FK, since Postgres has no native "FK to one of
# several tables" constraint - ownership of the referenced row is instead checked at the
# API layer (see api/v1/income.py's _validate_destination) every time one of these is
# created. A destination row can be deleted later without cascading here (no FK to
# cascade through), which just means a very old allocation/transaction can point at an
# account that no longer exists - the frontend should treat a lookup miss for account_id
# as "this account was deleted," not an error.
#
# STOCK_POSITION was added in Phase 5 for employer stock grants (RSUs) - an income
# allocation whose destination is a StockPosition, with vesting fields on IncomeAllocation
# itself (see models/income.py) mirroring how Phase 4.6 §8 added a pre-tax source_type for
# retirement destinations.
class AllocationDestinationType(str, Enum):
    BANK_ACCOUNT = "bank_account"
    RETIREMENT_ACCOUNT = "retirement_account"
    EDUCATION_ACCOUNT = "education_account"
    STOCK_POSITION = "stock_position"


# Where the money for a real (not simulated) retirement/education contribution actually
# came from - see api/v1/retirement_accounts.py and api/v1/education_accounts.py's
# record_contribution. Mirrors how real households fund these accounts: BANK_ACCOUNT is
# post-tax money moved from a checking/savings account (this actually debits that
# account's balance); PRE_TAX_SALARY is a payroll deduction that never touches a bank
# account balance in this app (money that was never "deposited" in the first place);
# TRACK_ONLY records the contribution with no effect on any other account's balance, for
# a user who just wants the number in one place without modeling where it came from.
class ContributionSourceType(str, Enum):
    BANK_ACCOUNT = "bank_account"
    PRE_TAX_SALARY = "pre_tax_salary"
    TRACK_ONLY = "track_only"


# What kind of real (posted, not simulated) money movement a Transaction row represents -
# see models/transactions.py. Every value here corresponds to exactly one place in the API
# that creates Transaction rows: logging an income occurrence, recording a retirement/
# education contribution, (Phase 5) an investment buy/sell/RSU vest, or (V2 scheduler)
# interest/expected-return credited to a bank, retirement, or education account.
#
# STOCK_SALE is deliberately reused for a bond or property sale too, not split into
# BOND_SALE/PROPERTY_SALE - see docs/phase5-plan.md's "Deliberate Scope Limits" for why:
# all three are "sold an investment, realized a P/L," and Transaction.account_type already
# disambiguates which table it hit. INTEREST is reused the same way across all three
# interest-bearing account types (bank/retirement/education) rather than split per type,
# for the identical reason - Transaction.account_type already disambiguates which one.
class TransactionType(str, Enum):
    INCOME = "income"
    RETIREMENT_CONTRIBUTION = "retirement_contribution"
    EDUCATION_CONTRIBUTION = "education_contribution"
    STOCK_PURCHASE = "stock_purchase"
    STOCK_SALE = "stock_sale"
    RSU_VEST = "rsu_vest"
    INTEREST = "interest"


# How often a bond pays coupon interest - drives investment_calculator.py's amortization
# schedule period count. Deliberately just these two (unlike RecurringAction's generic
# days/weeks/months): real-world bonds pay annually or semi-annually, not on arbitrary
# schedules.
class BondPaymentFrequency(str, Enum):
    ANNUALLY = "annually"
    SEMI_ANNUALLY = "semi_annually"


# The kind of event a StockTransaction row records against a StockPosition - see
# models/investments.py. BUY/SELL come from the user's own /buy and /sell actions; RSU_VEST
# comes from logging an Income occurrence whose allocation vests into this position (see
# services/income_posting.py's post_income_transactions and docs/phase5-plan.md §5).
class StockTransactionType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    RSU_VEST = "rsu_vest"
