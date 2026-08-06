/**
 * Plain-language explanations of 529/education-savings terms, shown via InfoTooltip
 * (components/ui/info-tooltip.tsx) throughout the Education module. Content is drawn from
 * the same 2026 research recorded in docs/phase4.5-plan.md and used by
 * backend/app/services/education_rules.py - if a figure or rule changes there, update the
 * wording here too so the two don't drift apart, the same rule Phase 4's
 * retirement/glossary.ts follows for its own content.
 */

export interface GlossaryEntry {
  title: string
  content: string
}

export const EDUCATION_GLOSSARY = {
  '529_plan': {
    title: '529 Plan',
    content:
      'A state-administered, tax-advantaged account for education savings. Contributions grow tax-free, and withdrawals are tax-free when used for qualified education expenses. Unlike a retirement account, the account owner and the beneficiary (the student) are different people.',
  },
  coverdell_esa: {
    title: 'Coverdell ESA',
    content:
      'A tax-advantaged education savings account with a much lower contribution cap than a 529 ($2,000/year) but broader qualified-expense rules for K-12. This app tracks the balance, but its own rules and limits aren\'t implemented yet.',
  },
  custodial_utma_ugma: {
    title: 'Custodial Account (UTMA/UGMA)',
    content:
      'A general-purpose custodial account held for a minor - not education-specific and with no special tax advantages, but no restrictions on how the funds are used once the minor reaches the age of majority. This app tracks the balance, but its own rules aren\'t implemented yet.',
  },
  beneficiary: {
    title: 'Beneficiary',
    content:
      "The student the account is for - distinct from the account owner (typically a parent or grandparent), who retains control. The beneficiary can be changed to another \"member of the family\" without tax consequences.",
  },
  plan_provider: {
    title: 'Plan Provider',
    content:
      'The state program administering the account, e.g. "NY 529 College Savings Program" or "Utah my529." You can open a 529 from any state regardless of where you live; informational only in this app, not tied to any calculation.',
  },
  qualified_expenses: {
    title: 'Qualified Education Expenses',
    content:
      'Tuition, fees, books, supplies, equipment, and room & board (if enrolled at least half-time) at any eligible post-secondary institution, plus computer/internet access, registered apprenticeship program costs, and OBBBA-expanded recognized postsecondary credential programs.',
  },
  k12_withdrawal_limit: {
    title: 'K-12 Withdrawal Limit',
    content:
      '$20,000 per student, per year (2026) - raised from $10,000 by the OBBBA (signed July 2025). Newly qualified as of 2026: curriculum materials, textbooks, tutoring outside the home, and standardized test fees (AP, SAT/ACT, etc).',
  },
  gift_tax_exclusion: {
    title: 'Annual Gift Tax Exclusion',
    content:
      "$19,000 per beneficiary in 2026 (or $38,000 for a married couple who elects gift-splitting on IRS Form 709). This is not a 529 contribution cap - it's the threshold above which a gift must be reported against the giver's lifetime gift/estate tax exemption. For nearly all users it's purely informational and never blocks a contribution.",
  },
  superfunding: {
    title: '5-Year Superfunding Election',
    content:
      "A donor may front-load 5 years of the annual gift-tax exclusion into one lump sum - $95,000 single / $190,000 married (2026) - via IRS Form 709 with 5-year averaging elected. Using it means no further annual-exclusion gifts to that same beneficiary for the next 5 years without exceeding the exclusion.",
  },
  roth_rollover: {
    title: '529-to-Roth IRA Rollover',
    content:
      "Up to $35,000 lifetime per beneficiary, tax/penalty-free, into a Roth IRA owned by the 529's beneficiary (SECURE 2.0 S126). Requires the 529 account to be open 15+ years, the specific funds rolled to be at least 5 years old, and the beneficiary to have earned income. The annual rollover amount counts toward the beneficiary's normal annual IRA limit.",
  },
  non_qualified_withdrawal_penalty: {
    title: 'Non-Qualified Withdrawal Penalty',
    content:
      "If you withdraw funds for something other than a qualified education expense, the earnings portion is taxed as ordinary income plus a 10% federal penalty. The contributions/basis portion is never taxed or penalized, since it was already after-tax money.",
  },
  student_loan_repayment: {
    title: 'Student Loan Repayment',
    content:
      'Up to $10,000 lifetime per borrower (the beneficiary, or each sibling separately) can be used toward qualified education loan principal/interest. Not inflation-indexed - unchanged since the original SECURE Act (2019).',
  },
  apprenticeship_credentialing: {
    title: 'Apprenticeship & Credentialing Programs',
    content:
      'Registered apprenticeship program fees, books, supplies, and equipment qualify (National Apprenticeship Act). OBBBA (2026) expanded qualified expenses to recognized postsecondary credential programs - WIOA-authorized, military credentials, and state/federal-approved certifications.',
  },
  state_aggregate_limit: {
    title: 'State Aggregate Balance Limit',
    content:
      'Each state sets its own lifetime aggregate balance cap per beneficiary across all 529s it administers, ranging from about $235,000 to $675,000. This is a per-state lifetime cap, not a federal or annual rule - and this app does not track or enforce it in v1.',
  },
  expected_return: {
    title: 'Expected Annual Return',
    content:
      "Your assumption for how much this account grows per year on average. It's a projection input, not a guarantee - actual markets vary year to year, and many 529 plans use age-based portfolios that grow more conservative as the beneficiary nears college age.",
  },
  ytd_contributions: {
    title: 'YTD (Year-to-Date) Contributions',
    content:
      "How much has been contributed to this account so far this calendar year - tracked here against this beneficiary's gift-tax exclusion, not an IRS contribution cap (529s have none).",
  },
} satisfies Record<string, GlossaryEntry>

export type GlossaryKey = keyof typeof EDUCATION_GLOSSARY
