/**
 * Thin wrappers around the /auth and /users/me backend endpoints, used by LoginPage and
 * RegisterPage. Kept separate from the Zustand authStore so these functions stay pure
 * data-fetching calls - the pages themselves decide when to write the result into state.
 */
import apiClient from '@/lib/api-client'
import type { User } from '@/types'

interface LoginResponse {
  access_token: string
  token_type: string
}

// Exchange email/password for a JWT access token.
export async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/auth/login', {
    email,
    password,
  })
  return response.data
}

// Create a new account; does not log the user in (call login() afterward).
export async function register(
  email: string,
  password: string,
  fullName?: string
): Promise<User> {
  const response = await apiClient.post<User>('/auth/register', {
    email,
    password,
    full_name: fullName,
  })
  return response.data
}

// Fetch the authenticated user's profile. Accepts an explicit `token` so callers can look
// up the profile for a token that hasn't been written to the authStore yet (e.g.
// immediately after login, before setAuth() has run).
export async function getCurrentUser(token?: string): Promise<User> {
  const response = await apiClient.get<User>('/users/me', {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  return response.data
}
