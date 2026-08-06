/**
 * Covers the login form's validation, the happy path (login -> fetch profile -> store
 * auth -> redirect), and the failure path (backend error surfaced to the user). The API
 * module and react-router-dom's navigation are mocked so these run without a backend.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AxiosError, AxiosHeaders } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LoginPage from './LoginPage'
import { useAuthStore } from '@/stores/authStore'
import * as authApi from '../api'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../api')

function renderLoginPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  useAuthStore.setState({ token: null, user: null, isAuthenticated: false })
})

describe('LoginPage', () => {
  it('renders accessible, labeled email and password fields', () => {
    renderLoginPage()

    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('shows validation errors instead of submitting when the form is empty', async () => {
    const user = userEvent.setup()
    renderLoginPage()

    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText('Invalid email address')).toBeInTheDocument()
    expect(authApi.login).not.toHaveBeenCalled()
  })

  it('logs in, loads the profile, stores auth state, and redirects to /dashboard', async () => {
    const user = userEvent.setup()
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: 'test-access-token',
      token_type: 'bearer',
    })
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      id: 'user-1',
      email: 'jd@example.com',
      full_name: 'JD',
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })

    renderLoginPage()

    await user.type(screen.getByLabelText('Email'), 'jd@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct-password')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/dashboard'))

    expect(authApi.login).toHaveBeenCalledWith('jd@example.com', 'correct-password')
    expect(authApi.getCurrentUser).toHaveBeenCalledWith('test-access-token')
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
    expect(useAuthStore.getState().token).toBe('test-access-token')
  })

  it('surfaces the backend error detail instead of a generic Axios message', async () => {
    const user = userEvent.setup()
    const axiosError = new AxiosError(
      'Request failed with status code 401',
      '401',
      undefined,
      undefined,
      {
        status: 401,
        statusText: 'Unauthorized',
        headers: new AxiosHeaders(),
        config: { headers: new AxiosHeaders() },
        data: { detail: 'Incorrect email or password' },
      }
    )
    vi.mocked(authApi.login).mockRejectedValue(axiosError)

    renderLoginPage()

    await user.type(screen.getByLabelText('Email'), 'jd@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong-password')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText('Incorrect email or password')).toBeInTheDocument()
    expect(mockNavigate).not.toHaveBeenCalled()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })
})
