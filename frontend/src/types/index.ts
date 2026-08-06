/**
 * Shared TypeScript types mirroring the Pydantic response schemas defined in the backend
 * (see backend/app/schemas). Numeric/decimal fields are typed as `string` because FastAPI
 * serializes Python Decimal values as JSON strings rather than numbers, and callers are
 * expected to run them through formatCurrency/parseFloat from lib/utils.ts as needed.
 */

// Mirrors backend/app/schemas/user.py:UserResponse.
export interface User {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

// Mirrors backend/app/schemas/bank_accounts.py:BankAccountResponse.
export interface BankAccount {
  id: string
  user_id: string
  account_name: string
  account_type: 'savings' | 'checking' | 'cd'
  principal: string
  current_balance: string
  interest_rate: string | null
  compounding_frequency: 'daily' | 'monthly' | 'quarterly' | 'annually'
  cd_start_date: string | null
  cd_term_months: number | null
  cd_auto_renew: boolean
  is_simulation: boolean
  created_at: string
  updated_at: string
}

// Mirrors backend/app/models/enums.py:ActionCategory - predetermined tags for a
// recurring action, kept separate from its free-text description for future
// spend/income analysis by category.
export type ActionCategory =
  | 'salary'
  | 'housing'
  | 'utilities'
  | 'insurance'
  | 'retirement'
  | 'investment'
  | 'healthcare'
  | 'entertainment'
  | 'transportation'
  | 'other'

// Mirrors backend/app/schemas/bank_accounts.py:RecurringActionResponse.
export interface RecurringAction {
  id: string
  bank_account_id: string
  action_type: 'deposit' | 'withdrawal'
  amount: string
  description: string | null
  category: ActionCategory | null
  frequency_value: number
  frequency_unit: 'days' | 'weeks' | 'months'
  start_date: string
  end_date: string | null
  next_execution_date: string
  is_active: boolean
  created_at: string
}

// Mirrors backend/app/schemas/bank_accounts.py:ProjectionPoint - one row of a simulation.
export interface ProjectionPoint {
  month: number
  date: string
  balance: string
  principal: string
  interest_earned: string
  deposits: string
  withdrawals: string
}

// Mirrors backend/app/schemas/bank_accounts.py:SimulationResponse.
export interface SimulationResponse {
  account_id: string
  projections: ProjectionPoint[]
  final_balance: string
  total_interest: string
  total_deposits: string
  total_withdrawals: string
}

// Mirrors backend/app/schemas/bank_accounts.py:AccountProjectionSeries - one account's
// (or CD renewal segment's, or the synthesized savings bucket's) series within a
// combined simulation. is_continuation is true for every CD renewal segment after the
// first - its first projection point duplicates the prior segment's last point (the
// same money, carried over at rollover), so anything that sums multiple series together
// (see components/charts/CombinedGrowthChart.tsx) must skip that duplicated point per
// series, or it double-counts that one shared month.
export interface AccountProjectionSeries {
  account_id: string
  account_name: string
  account_type: 'savings' | 'checking' | 'cd'
  compounding_frequency: 'daily' | 'monthly' | 'quarterly' | 'annually'
  is_virtual: boolean
  is_continuation: boolean
  projections: ProjectionPoint[]
}

// Mirrors backend/app/schemas/bank_accounts.py:CombinedTotalPoint.
export interface CombinedTotalPoint {
  month: number
  date: string
  total_balance: string
}

// Mirrors backend/app/schemas/bank_accounts.py:CombinedSimulationResponse - response
// for POST /bank-accounts/simulate-combined, driving the dashboard's combined chart.
export interface CombinedSimulationResponse {
  accounts: AccountProjectionSeries[]
  total_projections: CombinedTotalPoint[]
  final_total_balance: string
}

// Shape of a FastAPI HTTPException JSON body, as surfaced in Axios error responses.
export interface ApiError {
  detail: string
}

// Mirrors backend/app/models/enums.py:FilingStatus.
export type FilingStatus =
  | 'single'
  | 'married_filing_jointly'
  | 'married_filing_separately'
  | 'head_of_household'

// Mirrors backend/app/schemas/user.py:UserResponse - includes the Phase 4 profile fields
// (birth_date onward) that services/retirement_rules.py reads to compute contribution
// limits and eligibility.
export interface UserProfile extends User {
  birth_date: string | null
  filing_status: FilingStatus | null
  annual_income: string | null
  has_employer_retirement_plan: boolean
}

// Mirrors backend/app/models/enums.py:RetirementAccountType.
export type RetirementAccountType =
  | 'traditional_401k'
  | 'roth_401k'
  | 'traditional_ira'
  | 'roth_ira'
  | 'sep_ira'
  | 'simple_ira'
  | 'hsa'

// Mirrors backend/app/models/enums.py:VestingType.
export type VestingType = 'immediate' | 'cliff' | 'graded'

// Mirrors backend/app/schemas/retirement_accounts.py:RetirementAccountResponse.
export interface RetirementAccount {
  id: string
  user_id: string
  account_name: string
  account_type: RetirementAccountType
  balance: string
  contribution_ytd: string
  employer_name: string | null
  annual_salary: string | null
  employer_match_percent: string | null
  employer_match_limit_percent: string | null
  vesting_type: VestingType | null
  vesting_years: number | null
  vested_percent: string
  expected_return_rate: string
  is_simulation: boolean
  created_at: string
  updated_at: string
}

// Mirrors backend/app/models/enums.py:ContributionFrequency.
export type ContributionFrequency = 'monthly' | 'yearly'

// Mirrors backend/app/schemas/retirement_accounts.py:RecurringContributionResponse - a
// scheduled monthly or yearly contribution, feeding growth simulations automatically
// (see features/retirement/hooks/useRetirementAccounts.ts:useRetirementSimulation).
export interface RetirementRecurringContribution {
  id: string
  retirement_account_id: string
  amount: string
  frequency: ContributionFrequency
  start_date: string
  end_date: string | null
  is_active: boolean
  created_at: string
}

// Mirrors backend/app/schemas/retirement_accounts.py:ContributionLimitInfo - returned by
// both GET /retirement-accounts/limits and POST /retirement-accounts/{id}/contribute.
export interface ContributionLimitInfo {
  account_id: string | null
  account_type: RetirementAccountType
  employee_limit: string
  total_limit: string | null
  catch_up_eligible: boolean
  catch_up_amount: string
  contribution_ytd: string
  remaining_contribution: string
  employer_match_this_contribution: string | null
  eligible: boolean
  eligibility_note: string | null
  transaction_id: string | null
}

// Mirrors backend/app/schemas/retirement_accounts.py:RetirementProjectionPoint.
export interface RetirementProjectionPoint {
  month: number
  date: string
  balance: string
  employee_contributions: string
  employer_contributions: string
  growth: string
}

// Mirrors backend/app/schemas/retirement_accounts.py:RetirementSimulationResponse.
export interface RetirementSimulationResponse {
  account_id: string
  projections: RetirementProjectionPoint[]
  final_balance: string
  total_employee_contributions: string
  total_employer_contributions: string
  total_growth: string
}

// Mirrors backend/app/models/enums.py:EducationAccountType.
export type EducationAccountType = '529_plan' | 'coverdell_esa' | 'custodial_utma_ugma'

// Mirrors backend/app/schemas/education_accounts.py:EducationAccountResponse. Unlike
// RetirementAccount, the beneficiary (the student) is a distinct person from the owning
// user, so this carries beneficiary_name/beneficiary_birth_date instead of any
// employer/vesting fields.
export interface EducationAccount {
  id: string
  user_id: string
  account_name: string
  account_type: EducationAccountType
  beneficiary_name: string
  beneficiary_birth_date: string | null
  plan_provider: string | null
  balance: string
  contribution_ytd: string
  expected_return_rate: string
  is_simulation: boolean
  created_at: string
  updated_at: string
}

// Mirrors backend/app/schemas/education_accounts.py:RecurringContributionResponse - a
// scheduled monthly or yearly contribution, feeding growth simulations automatically
// (see features/education/hooks/useEducationAccounts.ts:useEducationSimulation). Reuses
// the same ContributionFrequency type as RetirementRecurringContribution.
export interface EducationRecurringContribution {
  id: string
  education_account_id: string
  amount: string
  frequency: ContributionFrequency
  start_date: string
  end_date: string | null
  is_active: boolean
  created_at: string
}

// Mirrors backend/app/schemas/education_accounts.py:GiftTaxInfo - returned by both
// GET /education-accounts/gift-tax-info and POST /education-accounts/{id}/contribute.
// Deliberately has no `eligible`/blocking field, unlike ContributionLimitInfo: a 529 has
// no IRS contribution cap, only a gift-tax *reporting* threshold, so this is purely
// informational.
export interface GiftTaxInfo {
  account_id: string | null
  beneficiary_name: string
  annual_exclusion: string
  superfunding_lump_sum: string
  beneficiary_contribution_ytd: string
  remaining_before_exclusion: string
  would_exceed_exclusion: boolean
  note: string
  transaction_id: string | null
}

// Mirrors backend/app/models/enums.py:ContributionSourceType - where the money for a real
// retirement/education contribution actually came from. Sent on
// POST /retirement-accounts/{id}/contribute and POST /education-accounts/{id}/contribute.
export type ContributionSourceType = 'bank_account' | 'pre_tax_salary' | 'track_only'

// Mirrors backend/app/schemas/education_accounts.py:EducationProjectionPoint. No
// employee/employer split - 529s aren't employer-sponsored, unlike RetirementProjectionPoint.
export interface EducationProjectionPoint {
  month: number
  date: string
  balance: string
  contributions: string
  growth: string
}

// Mirrors backend/app/schemas/education_accounts.py:EducationSimulationResponse.
export interface EducationSimulationResponse {
  account_id: string
  projections: EducationProjectionPoint[]
  final_balance: string
  total_contributions: string
  total_growth: string
}

// Mirrors backend/app/models/enums.py:ReceiptProcessingStatus.
export type ReceiptProcessingStatus = 'pending' | 'processing' | 'completed' | 'needs_review' | 'failed'

// Mirrors backend/app/models/enums.py:ExtractionMethod.
export type ExtractionMethod = 'tesseract' | 'pdf_text' | 'pdf_ocr' | 'manual'

// Mirrors backend/app/schemas/receipts.py:ReceiptLineItemResponse.
export interface ReceiptLineItem {
  id: string
  description: string | null
  quantity: string | null
  unit_price: string | null
  total_price: string | null
  line_order: number | null
}

// Mirrors backend/app/schemas/receipts.py:ReceiptResponse. file_url is a freshly
// generated presigned MinIO/S3 URL on every response, not a stored value - see that
// schema's docstring.
export interface Receipt {
  id: string
  user_id: string
  original_filename: string
  file_url: string
  file_type: string
  file_size_bytes: number | null

  processing_status: ReceiptProcessingStatus
  processing_error: string | null
  processed_at: string | null
  extraction_method: ExtractionMethod | null

  merchant_name: string | null
  merchant_name_confidence: string | null
  total_amount: string | null
  total_amount_confidence: string | null
  transaction_date: string | null
  transaction_date_confidence: string | null

  tax_amount: string | null
  subtotal_amount: string | null
  payment_method: string | null
  receipt_number: string | null

  user_verified: boolean
  verified_at: string | null

  created_at: string
  updated_at: string
}

// Mirrors backend/app/schemas/receipts.py:ReceiptDetailResponse - the review/detail view,
// with line items attached (the list endpoint returns the lighter Receipt shape above).
export interface ReceiptDetail extends Receipt {
  line_items: ReceiptLineItem[]
}

// Mirrors backend/app/schemas/receipts.py:ReceiptUploadResultItem - one per file in a
// batch upload; receipt_id/status are null and error is set when a file was rejected
// before a Receipt row was even created (unsupported type, over the size limit).
export interface ReceiptUploadResultItem {
  filename: string
  receipt_id: string | null
  status: ReceiptProcessingStatus | null
  error: string | null
}

export interface ReceiptUploadResponse {
  results: ReceiptUploadResultItem[]
}

// Mirrors backend/app/models/expense_categories.py:ExpenseCategory.
export interface ExpenseCategory {
  id: string
  user_id: string
  name: string
  color: string | null
  icon: string | null
  monthly_budget: string | null
  is_system: boolean
  created_at: string
}

// Mirrors backend/app/schemas/expenses.py:ExpenseResponse.
export interface Expense {
  id: string
  user_id: string
  receipt_id: string | null
  merchant_name: string
  amount: string
  expense_date: string
  category_id: string | null
  bank_account_id: string | null
  description: string | null
  tags: string[] | null
  is_recurring: boolean
  recurrence_pattern: string | null
  created_at: string
  updated_at: string
}

// Mirrors backend/app/schemas/expenses.py:ExpenseCategorySummary.
export interface ExpenseCategorySummaryItem {
  category_id: string | null
  category_name: string
  category_color: string | null
  total_amount: string
  expense_count: number
}

// Mirrors backend/app/schemas/expenses.py:ExpenseSummaryResponse.
export interface ExpenseSummaryResponse {
  start_date: string
  end_date: string
  total_amount: string
  expense_count: number
  by_category: ExpenseCategorySummaryItem[]
}

// --- Income -----------------------------------------------------------------

// Mirrors backend/app/models/enums.py:IncomeFrequency.
export type IncomeFrequency = 'weekly' | 'biweekly' | 'semi_monthly' | 'monthly'

// Mirrors backend/app/models/enums.py:AllocationDestinationType - which kind of account
// an IncomeAllocation or Transaction points at. 'stock_position' was added in Phase 5 for
// employer stock grants (RSUs).
export type AllocationDestinationType =
  | 'bank_account'
  | 'retirement_account'
  | 'education_account'
  | 'stock_position'

// Mirrors backend/app/schemas/income.py:IncomeAllocationResponse. `source_type` is the
// Phase 4.6 "Option A" pre-tax-deduction field (see docs/phase4.6-money-flow-plan.md's
// Next Steps §8) - only ever 'pre_tax_salary' on a retirement/education destination, or
// null/undefined for an ordinary allocation. `rsu_vesting_type`/`rsu_vesting_years`/
// `rsu_cliff_date`/`rsu_total_shares`/`rsu_shares_vested` are the Phase 5 equivalent for a
// 'stock_position' destination - see docs/phase5-plan.md §2. `rsu_shares_vested` is a
// running total the backend maintains; never set it from the frontend.
export interface IncomeAllocation {
  id: string
  destination_type: AllocationDestinationType
  destination_id: string
  percentage: string
  source_type: ContributionSourceType | null
  rsu_vesting_type: VestingType | null
  rsu_vesting_years: number | null
  rsu_cliff_date: string | null
  rsu_total_shares: string | null
  rsu_shares_vested: string
}

// Mirrors backend/app/schemas/income.py:IncomeResponse.
export interface Income {
  id: string
  user_id: string
  name: string
  amount: string
  is_recurring: boolean
  frequency: IncomeFrequency | null
  start_date: string | null
  income_date: string | null
  is_active: boolean
  allocations: IncomeAllocation[]
  created_at: string
  updated_at: string
}

// Mirrors backend/app/schemas/income.py:LogIncomeResponse.
export interface LogIncomeResponse {
  income_id: string
  total_amount: string
  log_date: string
  transactions: Transaction[]
}

// --- Transactions -------------------------------------------------------------

// Mirrors backend/app/models/enums.py:TransactionType. The three stock_* values were
// added in Phase 5 - see backend/app/api/v1/transactions.py's docstring for why
// transactions of these types can't be edited/deleted from the unified log. 'interest'
// was added for the V2 background scheduler (see docs/future-plan.md) - bank account
// interest and retirement/education expected-return credits, disambiguated by
// `account_type` the same way 'stock_sale' already covers stocks/bonds/property.
export type TransactionType =
  | 'income'
  | 'retirement_contribution'
  | 'education_contribution'
  | 'stock_purchase'
  | 'stock_sale'
  | 'rsu_vest'
  | 'interest'

// Mirrors backend/app/schemas/transactions.py:TransactionResponse - the unified,
// editable/deletable log of every real (posted, not simulated) money movement this app
// has recorded: income occurrences, retirement/education contributions, investment
// trades, and interest/expected-return credits. Expenses are never stored as rows in
// this table - see backend/app/models/transactions.py's docstring - though
// TransactionsPage merges them in for display; see that page's own docstring.
export interface Transaction {
  id: string
  user_id: string
  transaction_type: TransactionType
  amount: string
  transaction_date: string
  description: string | null
  account_type: AllocationDestinationType | null
  account_id: string | null
  income_id: string | null
  source_type: ContributionSourceType | null
  source_bank_account_id: string | null
  created_at: string
  updated_at: string
}

// Mirrors backend/app/schemas/scheduler.py:SchedulerRunResponse - the result of manually
// triggering the V2 background scheduler (POST /scheduler/run) instead of waiting for its
// daily Celery Beat tick. Each count is occurrences posted, not rules touched - one
// Income catching up 12 months contributes 12 to incomes_posted, not 1.
export interface SchedulerRunResult {
  as_of: string
  incomes_posted: number
  bank_interest_applied: number
  retirement_interest_applied: number
  education_interest_applied: number
  retirement_contributions_posted: number
  education_contributions_posted: number
  expenses_created: number
}

// --- Investments (Phase 5) -----------------------------------------------------------

// Mirrors backend/app/models/enums.py:BondPaymentFrequency.
export type BondPaymentFrequency = 'annually' | 'semi_annually'

// Mirrors backend/app/models/enums.py:StockTransactionType.
export type StockTransactionType = 'buy' | 'sell' | 'rsu_vest'

// Mirrors backend/app/schemas/investments.py:StockPositionResponse. `market_value`/
// `unrealized_pnl` are null whenever `current_price` hasn't been fetched yet - see that
// schema's docstring.
export interface StockPosition {
  id: string
  user_id: string
  ticker_symbol: string
  shares: string
  average_cost_per_share: string
  current_price: string | null
  last_price_update: string | null
  market_value: string | null
  unrealized_pnl: string | null
  // Account a sell's proceeds will be credited back into - see
  // backend/app/models/investments.py:StockPosition's docstring.
  funding_bank_account_id: string | null
  is_simulation: boolean
  created_at: string
  updated_at: string
}

// Mirrors backend/app/schemas/investments.py:StockTransactionResponse.
export interface StockTransaction {
  id: string
  stock_position_id: string
  transaction_type: StockTransactionType
  shares: string
  price_per_share: string
  transaction_date: string
  realized_pnl: string | null
  source_bank_account_id: string | null
  notes: string | null
  created_at: string
}

// Mirrors backend/app/schemas/investments.py:StockHistoryPoint.
export interface StockHistoryPoint {
  date: string
  open: string
  high: string
  low: string
  close: string
  volume: number
}

// Mirrors backend/app/schemas/investments.py:StockHistoryResponse.
export interface StockHistoryResponse {
  ticker: string
  period: string
  data: StockHistoryPoint[]
}

// Time-range buttons the stock chart offers - see api/v1/investments.py's
// VALID_HISTORY_PERIODS in services/stock_price.py.
export type StockHistoryPeriod = '1d' | '1mo' | '3mo' | '1y' | '5y'

// Mirrors backend/app/schemas/investments.py:BondHoldingResponse. `current_book_value` is
// computed server-side via the straight-line amortization method - see
// services/investment_calculator.py.
export interface BondHolding {
  id: string
  user_id: string
  name: string
  purchase_price: string
  face_value: string
  coupon_rate: string
  payment_frequency: BondPaymentFrequency
  purchase_date: string
  maturity_date: string
  is_simulation: boolean
  is_active: boolean
  sale_price: string | null
  sale_date: string | null
  realized_pnl: string | null
  current_book_value: string
  created_at: string
  updated_at: string
}

// Mirrors backend/app/schemas/investments.py:BondAmortizationPeriod.
export interface BondAmortizationPeriod {
  period_date: string
  coupon_payment: string
  amortization_amount: string
  book_value: string
}

// Mirrors backend/app/schemas/investments.py:BondAmortizationScheduleResponse.
export interface BondAmortizationSchedule {
  bond_id: string
  schedule: BondAmortizationPeriod[]
}

// Mirrors backend/app/schemas/investments.py:PropertyInvestmentResponse.
export interface PropertyInvestment {
  id: string
  user_id: string
  name: string
  cost: string
  expected_return_rate: string
  purchase_date: string
  is_simulation: boolean
  is_active: boolean
  sale_price: string | null
  sale_date: string | null
  realized_pnl: string | null
  current_value: string
  created_at: string
  updated_at: string
}

// Mirrors backend/app/schemas/investments.py:InvestmentSummaryResponse - powers the
// dashboard's net-worth aggregation.
export interface InvestmentSummary {
  total_stocks_value: string
  total_bonds_value: string
  total_property_value: string
  total_value: string
  total_unrealized_pnl: string
}
