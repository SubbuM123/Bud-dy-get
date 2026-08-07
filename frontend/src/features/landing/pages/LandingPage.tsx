/**
 * Public entry page shown at "/" to a signed-out visitor (App.tsx sends an already
 * authenticated session straight to /dashboard instead - see RootRoute there). The
 * "preview" panel below is a static mockup built from the same Card/color tokens the real
 * DashboardPage uses, not a screenshot - that keeps it visually honest (it'll never drift
 * out of sync with a real design change the way a stale screenshot would) and avoids ever
 * putting real account data on a public, unauthenticated page.
 */
import { Link } from 'react-router-dom'
import { Wallet, Landmark, TrendingUp, PiggyBank, ArrowUpRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <span className="text-xl font-bold text-slate-900">Bud(dy)get</span>
        <div className="flex items-center gap-3">
          <Link to="/login">
            <Button variant="ghost">Log in</Button>
          </Link>
          <Link to="/register">
            <Button>Sign up</Button>
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-20 pt-10">
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
              Every account, every dollar, one place.
            </h1>
            <p className="mt-4 text-lg text-slate-600">
              Bud(dy)get brings your bank accounts, income, expenses, investments, and
              retirement savings together so you always know where you stand - and it
              catches up on its own, even if you only check in once in a while.
            </p>
            <div className="mt-8 flex gap-4">
              <Link to="/register">
                <Button size="lg">Get started free</Button>
              </Link>
              <Link to="/login">
                <Button size="lg" variant="outline">
                  Log in
                </Button>
              </Link>
            </div>
          </div>

          <div className="rounded-xl border bg-white p-3 shadow-xl">
            <div className="flex items-center gap-1.5 border-b px-2 pb-3">
              <span className="h-2.5 w-2.5 rounded-full bg-danger-500" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
              <span className="h-2.5 w-2.5 rounded-full bg-success-500" />
              <span className="ml-3 text-xs text-slate-400">app.buddyget.com/dashboard</span>
            </div>

            <div className="space-y-4 p-4">
              <div>
                <p className="text-sm text-slate-500">Net Worth</p>
                <p className="text-3xl font-bold text-slate-900">$128,450</p>
                <p className="flex items-center gap-1 text-sm text-success-600">
                  <ArrowUpRight className="h-4 w-4" />
                  4.2% this month
                </p>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <Card className="shadow-none">
                  <CardContent className="flex flex-col items-center gap-1.5 p-3 text-center">
                    <div className="rounded-full bg-primary-100 p-2">
                      <Landmark className="h-4 w-4 text-primary-600" />
                    </div>
                    <p className="text-xs text-slate-500">Banking</p>
                    <p className="text-sm font-semibold">$24,180</p>
                  </CardContent>
                </Card>
                <Card className="shadow-none">
                  <CardContent className="flex flex-col items-center gap-1.5 p-3 text-center">
                    <div className="rounded-full bg-success-500/10 p-2">
                      <PiggyBank className="h-4 w-4 text-success-600" />
                    </div>
                    <p className="text-xs text-slate-500">Retirement</p>
                    <p className="text-sm font-semibold">$61,920</p>
                  </CardContent>
                </Card>
                <Card className="shadow-none">
                  <CardContent className="flex flex-col items-center gap-1.5 p-3 text-center">
                    <div className="rounded-full bg-amber-500/10 p-2">
                      <TrendingUp className="h-4 w-4 text-amber-600" />
                    </div>
                    <p className="text-xs text-slate-500">Investments</p>
                    <p className="text-sm font-semibold">$42,350</p>
                  </CardContent>
                </Card>
              </div>

              <Card className="shadow-none">
                <CardContent className="p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <p className="text-sm font-medium text-slate-700">Growth, last 6 months</p>
                    <Wallet className="h-4 w-4 text-slate-400" />
                  </div>
                  <svg viewBox="0 0 300 80" className="h-16 w-full" preserveAspectRatio="none">
                    <polyline
                      points="0,65 50,58 100,50 150,52 200,32 250,24 300,10"
                      fill="none"
                      stroke="rgb(37 99 235)"
                      strokeWidth="3"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
