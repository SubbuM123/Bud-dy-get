/**
 * Fixed left navigation rail listing every top-level module of the app (Dashboard, Bank
 * Accounts, Expenses, Receipts, Retirement, Education, Investments, Stock Portfolio,
 * Planning). Rendered once by MainLayout and shared across every authenticated page;
 * routes that don't have a real page yet still appear here so the full planned app
 * structure is visible from V1. "Investments" (Phase 5) covers bonds and property
 * investments; "Stock Portfolio" covers individual stock positions - split across two
 * pages rather than one crowded page (see docs/progress.md's 2026-08-04 "Phase 5 UI
 * split" entry) and named for a future merge with options trading once that's built.
 */
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Landmark,
  Wallet,
  ArrowLeftRight,
  Receipt,
  ScanLine,
  PiggyBank,
  GraduationCap,
  TrendingUp,
  LineChart,
  Calculator,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// One entry per top-level route; icon comes from lucide-react. `beta: true` renders a
// small "Beta" badge next to the label - see docs/plan.md's "Unified Money Flow Reform":
// Receipts is a standalone OCR/digitization tool for v1, deliberately disconnected from
// the rest of the app's money flow (Income -> Bank Accounts -> destinations).
const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Income', href: '/income', icon: Wallet },
  { name: 'Bank Accounts', href: '/bank-accounts', icon: Landmark },
  { name: 'Transactions', href: '/transactions', icon: ArrowLeftRight },
  { name: 'Expenses', href: '/expenses', icon: Receipt },
  { name: 'Receipts', href: '/receipts', icon: ScanLine, beta: true },
  { name: 'Retirement', href: '/retirement', icon: PiggyBank },
  { name: 'Education', href: '/education', icon: GraduationCap },
  { name: 'Investments', href: '/investments', icon: TrendingUp },
  { name: 'Stock Portfolio', href: '/stocks', icon: LineChart },
  { name: 'Planning', href: '/planning', icon: Calculator },
]

export default function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-50 w-64 bg-slate-900">
      <div className="flex h-16 items-center px-6">
        <h1 className="text-xl font-bold text-white">Bud(dy)get</h1>
      </div>

      <nav className="mt-6 px-3">
        <ul className="space-y-1">
          {navigation.map((item) => (
            <li key={item.name}>
              <NavLink
                to={item.href}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary-600 text-white'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  )
                }
              >
                <item.icon className="h-5 w-5" />
                {item.name}
                {item.beta && (
                  <span className="ml-auto rounded-full bg-slate-700 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-300">
                    Beta
                  </span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}
