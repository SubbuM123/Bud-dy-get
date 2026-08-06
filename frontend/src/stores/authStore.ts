/**
 * Global client-side auth state, backed by Zustand with localStorage persistence. This
 * store holds the JWT access token and the logged-in user's profile, and is the single
 * source of truth that both the Axios interceptor (lib/api-client.ts) and route guards
 * (App.tsx's ProtectedRoute) read from. Persisting to localStorage lets a session survive
 * a page refresh without requiring a fresh login.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  email: string
  full_name: string | null
}

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  setAuth: (token: string, user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      // Store a freshly issued token + user profile after a successful login/register.
      setAuth: (token, user) =>
        set({ token, user, isAuthenticated: true }),
      // Clear the session, e.g. on explicit logout or when the API returns a 401.
      logout: () =>
        set({ token: null, user: null, isAuthenticated: false }),
    }),
    {
      name: 'auth-storage',
    }
  )
)
