/**
 * Shell layout wrapping every authenticated route: fixed Sidebar on the left, Header
 * across the top, and the active page rendered via React Router's <Outlet /> in the
 * remaining space. App.tsx mounts this as the element for the top-level protected route
 * so individual pages never need to re-render the sidebar/header themselves.
 */
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'

export default function MainLayout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <Sidebar />

      <div className="pl-64">
        <Header />
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
