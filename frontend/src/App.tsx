/**
 * Top-level route table for the app. Splits routes into public (/, /login, /register) and
 * protected (everything under MainLayout, guarded by ProtectedRoute) groups. The protected
 * group is a pathless layout route - its children use absolute paths ("/dashboard" rather
 * than "dashboard") so "/" itself is free for RootRoute to own, rather than being claimed
 * by an index route the way it was before LandingPage existed. /investments (Phase 5)
 * covers bonds and property investments; /stocks covers individual stock positions
 * (StockPortfolioPage) - split across two pages rather than one crowded page, see
 * docs/progress.md's 2026-08-04 "Phase 5 UI split" entry. /stocks is named for a future
 * merge with options trading once that's built (see components/layout/Sidebar.tsx).
 */
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import MainLayout from './components/layout/MainLayout'
import LandingPage from './features/landing/pages/LandingPage'
import LoginPage from './features/auth/pages/LoginPage'
import RegisterPage from './features/auth/pages/RegisterPage'
import DashboardPage from './features/dashboard/pages/DashboardPage'
import NetWorthPage from './features/dashboard/pages/NetWorthPage'
import BankAccountsPage from './features/bank-accounts/pages/BankAccountsPage'
import AccountDetailPage from './features/bank-accounts/pages/AccountDetailPage'
import RetirementAccountsPage from './features/retirement/pages/RetirementAccountsPage'
import RetirementAccountDetailPage from './features/retirement/pages/RetirementAccountDetailPage'
import EducationAccountsPage from './features/education/pages/EducationAccountsPage'
import EducationAccountDetailPage from './features/education/pages/EducationAccountDetailPage'
import ExpensesPage from './features/expenses/pages/ExpensesPage'
import ReceiptsPage from './features/expenses/pages/ReceiptsPage'
import ReceiptDetailPage from './features/expenses/pages/ReceiptDetailPage'
import CategoriesPage from './features/expenses/pages/CategoriesPage'
import IncomePage from './features/income/pages/IncomePage'
import TransactionsPage from './features/transactions/pages/TransactionsPage'
import InvestmentsPage from './features/investments/pages/InvestmentsPage'
import StockPortfolioPage from './features/investments/pages/StockPortfolioPage'

// Route guard that redirects to /login when there is no authenticated session.
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// "/" itself: LandingPage for a signed-out visitor, straight to the dashboard for an
// already-authenticated one (so returning users skip the marketing page).
function RootRoute() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <LandingPage />
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<RootRoute />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/net-worth" element={<NetWorthPage />} />
        <Route path="/income" element={<IncomePage />} />
        <Route path="/transactions" element={<TransactionsPage />} />
        <Route path="/bank-accounts" element={<BankAccountsPage />} />
        <Route path="/bank-accounts/:accountId" element={<AccountDetailPage />} />
        <Route path="/expenses" element={<ExpensesPage />} />
        <Route path="/expense-categories" element={<CategoriesPage />} />
        <Route path="/receipts" element={<ReceiptsPage />} />
        <Route path="/receipts/:receiptId" element={<ReceiptDetailPage />} />
        <Route path="/retirement" element={<RetirementAccountsPage />} />
        <Route path="/retirement/:accountId" element={<RetirementAccountDetailPage />} />
        <Route path="/education" element={<EducationAccountsPage />} />
        <Route path="/education/:accountId" element={<EducationAccountDetailPage />} />
        <Route path="/investments" element={<InvestmentsPage />} />
        <Route path="/stocks" element={<StockPortfolioPage />} />
      </Route>
    </Routes>
  )
}

export default App
