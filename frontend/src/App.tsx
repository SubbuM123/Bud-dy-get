/**
 * Top-level route table for the app. Splits routes into public (/login, /register) and
 * protected (everything under MainLayout, guarded by ProtectedRoute) groups. Feature
 * routes that don't have a real page yet (planning) render an inline placeholder so the
 * full navigation structure is in place from V1, ready to be swapped for real pages as
 * each module is built. /investments (Phase 5) covers bonds and property investments;
 * /stocks covers individual stock positions (StockPortfolioPage) - split across two
 * pages rather than one crowded page, see docs/progress.md's 2026-08-04 "Phase 5 UI
 * split" entry. /stocks is named for a future merge with options trading once that's
 * built (see components/layout/Sidebar.tsx).
 */
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import MainLayout from './components/layout/MainLayout'
import LoginPage from './features/auth/pages/LoginPage'
import RegisterPage from './features/auth/pages/RegisterPage'
import DashboardPage from './features/dashboard/pages/DashboardPage'
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

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="income" element={<IncomePage />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="bank-accounts" element={<BankAccountsPage />} />
        <Route path="bank-accounts/:accountId" element={<AccountDetailPage />} />
        <Route path="expenses" element={<ExpensesPage />} />
        <Route path="expense-categories" element={<CategoriesPage />} />
        <Route path="receipts" element={<ReceiptsPage />} />
        <Route path="receipts/:receiptId" element={<ReceiptDetailPage />} />
        <Route path="retirement" element={<RetirementAccountsPage />} />
        <Route path="retirement/:accountId" element={<RetirementAccountDetailPage />} />
        <Route path="education" element={<EducationAccountsPage />} />
        <Route path="education/:accountId" element={<EducationAccountDetailPage />} />
        <Route path="investments" element={<InvestmentsPage />} />
        <Route path="stocks" element={<StockPortfolioPage />} />
        <Route path="planning" element={<div className="p-6">Financial Planning - Coming Soon</div>} />
      </Route>
    </Routes>
  )
}

export default App
