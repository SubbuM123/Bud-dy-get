/**
 * Plain-language explanations of retirement account types and terms, shown via
 * InfoTooltip (components/ui/info-tooltip.tsx) throughout the Retirement module. Content
 * is drawn from the same 2026 IRS research recorded in docs/phase4-plan.md and enforced
 * by backend/app/services/retirement_rules.py - if a limit or rule changes there, update
 * the wording here too so the two don't drift apart.
 */

export interface GlossaryEntry {
  title: string
  content: string
}

export const RETIREMENT_GLOSSARY = {
  traditional_401k: {
    title: 'Traditional 401(k)',
    content:
      "An employer-sponsored account funded with pre-tax paycheck deductions - contributions lower your taxable income now, but withdrawals in retirement are taxed as ordinary income. 2026 employee limit: $24,500 (more with catch-up if you're 50+).",
  },
  roth_401k: {
    title: 'Roth 401(k)',
    content:
      "Same employer plan and contribution limits as a Traditional 401(k), but funded with after-tax money - no deduction now, but qualified withdrawals in retirement are entirely tax-free. Unlike a Roth IRA, there's no income limit to contribute.",
  },
  traditional_ira: {
    title: 'Traditional IRA',
    content:
      "An individual (not employer-tied) account funded with contributions that may be tax-deductible depending on your income and whether you or your spouse are covered by a workplace plan. Shares one combined $7,500 (2026, under 50) limit with any Roth IRA you also have.",
  },
  roth_ira: {
    title: 'Roth IRA',
    content:
      "An individual account funded with after-tax money; qualified withdrawals are tax-free. Eligibility phases out at higher incomes (2026: Single $153k-$168k, Married Filing Jointly $242k-$252k). Shares one combined $7,500 (under 50) limit with any Traditional IRA you also have.",
  },
  sep_ira: {
    title: 'SEP IRA',
    content:
      'A retirement plan typically used by self-employed people or small business owners; only the employer (which may be you) contributes. This app tracks the balance, but contribution-limit enforcement for SEP IRAs isn\'t implemented yet.',
  },
  simple_ira: {
    title: 'SIMPLE IRA',
    content:
      'A simplified employer plan for small businesses, with lower contribution limits than a 401(k) but mandatory employer contributions. This app tracks the balance, but contribution-limit enforcement for SIMPLE IRAs isn\'t implemented yet.',
  },
  hsa: {
    title: 'HSA (Health Savings Account)',
    content:
      "Paired with a high-deductible health plan, an HSA has a \"triple tax advantage\": deductible contributions, tax-free growth, and tax-free withdrawals for qualified medical expenses. 2026 limits: $4,400 self-only / $8,750 family coverage.",
  },
  employer_match: {
    title: 'Employer Match',
    content:
      'Free money your employer adds to your 401(k) when you contribute, up to a limit - e.g. "50% match up to 6% of salary" means for every dollar you contribute (up to 6% of your pay), your employer adds 50 cents.',
  },
  match_limit: {
    title: 'Match Limit',
    content:
      'The share of your salary your employer will match contributions against - contributing beyond this percentage still grows your own balance, but stops earning additional match.',
  },
  vesting: {
    title: 'Vesting',
    content:
      "How much of your employer's contributions you actually get to keep if you leave the company. Immediate vesting means it's yours right away; cliff and graded vesting make you wait (see the Vesting Schedule tooltip for the difference).",
  },
  vesting_type: {
    title: 'Vesting Schedule',
    content:
      'Immediate: 100% yours right away. Cliff: 0% until a set number of years, then 100% all at once. Graded: vests gradually, an equal fraction each year, until fully vested.',
  },
  catch_up: {
    title: 'Catch-Up Contribution',
    content:
      "An extra amount people 50 and older can contribute on top of the normal limit, meant to help late starters save more as retirement nears. For a 401(k) in 2026 it's $8,000 (or $11,250 for ages 60-63, a \"super\" catch-up); for an IRA it's $1,100.",
  },
  magi: {
    title: 'MAGI (Modified Adjusted Gross Income)',
    content:
      "Roughly your gross income with a few specific deductions added back - the number the IRS actually uses to decide Roth IRA eligibility and Traditional IRA deductibility. This app uses your Annual Income field as a stand-in for MAGI.",
  },
  filing_status: {
    title: 'Tax Filing Status',
    content:
      "How you file your taxes (Single, Married Filing Jointly, etc.) - it changes the income thresholds at which Roth IRA eligibility and Traditional IRA deductibility phase out.",
  },
  contribution_limit: {
    title: '2026 Contribution Limit',
    content:
      'The maximum the IRS allows you to contribute to this type of account this year, based on your age (for catch-up eligibility) and, for Roth/Traditional IRA, your income and filing status.',
  },
  ytd_contributions: {
    title: 'YTD (Year-to-Date) Contributions',
    content:
      "How much you've contributed to this account so far this calendar year, tracked against the annual limit - contribution limits reset every January 1st.",
  },
  expected_return: {
    title: 'Expected Annual Return',
    content:
      "Your assumption for how much this account grows per year on average (e.g. 7% is a common long-run assumption for a diversified stock portfolio). It's a projection input, not a guarantee - actual markets vary year to year.",
  },
} satisfies Record<string, GlossaryEntry>

export type GlossaryKey = keyof typeof RETIREMENT_GLOSSARY
