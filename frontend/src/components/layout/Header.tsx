/**
 * Top bar shown above the page content on every authenticated route, displaying the
 * logged-in user's name/email and a logout button. Reads directly from the Zustand
 * authStore rather than props since it needs no data from its parent (MainLayout).
 */
import { LogOut, User } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { Button } from '@/components/ui/button'

export default function Header() {
  const { user, logout } = useAuthStore()

  return (
    <header className="sticky top-0 z-40 border-b bg-white">
      <div className="flex h-16 items-center justify-between px-6">
        <div />

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <User className="h-4 w-4" />
            <span>{user?.full_name || user?.email}</span>
          </div>

          <Button variant="ghost" size="sm" onClick={logout}>
            <LogOut className="h-4 w-4 mr-2" />
            Logout
          </Button>
        </div>
      </div>
    </header>
  )
}
