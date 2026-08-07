/**
 * Shell layout wrapping every authenticated route: fixed Sidebar on the left, Header
 * across the top, and the active page rendered via React Router's <Outlet /> in the
 * remaining space. App.tsx mounts this as the element for the top-level protected route
 * so individual pages never need to re-render the sidebar/header themselves.
 *
 * Also fires the background scheduler catch-up (services/scheduler.py, via
 * useRunScheduler) exactly once per authenticated session, right when the protected app
 * shell first mounts - see backend/app/api/v1/scheduler.py's docstring for why a
 * login-triggered run replaces a fixed daily schedule for an app used this infrequently.
 * Fire-and-forget: a failed background sync shouldn't block the UI, and the "Sync
 * Recurring Items" button (features/transactions) is still there as a manual fallback.
 */
import { useEffect, useRef } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import { useRunScheduler } from '@/features/scheduler/hooks/useScheduler'

export default function MainLayout() {
  const runScheduler = useRunScheduler()
  const hasRunRef = useRef(false)

  useEffect(() => {
    if (hasRunRef.current) return
    hasRunRef.current = true
    runScheduler.mutate(undefined, {
      onError: (error) => console.warn('Background scheduler catch-up failed:', error),
    })
    // Runs once on mount only - deliberately not depending on runScheduler, which is a
    // new object identity every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar />

      <div className="pl-64">
        <Header />
        <main className="p-6">
          <Outlet />
        </main>
        <footer className="py-6 text-center text-sm text-slate-500">
          Bud(dy)get &middot; &copy; 2026 Bud(dy)get. All rights reserved.
        </footer>
      </div>
    </div>
  )
}
