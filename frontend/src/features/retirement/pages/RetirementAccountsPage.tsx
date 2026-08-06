/**
 * List view for the Retirement Accounts module, mounted at /retirement. Mirrors
 * BankAccountsPage's structure: every account as a horizontally-scrollable strip of
 * cards, an inline "create account" form, an inline "edit account" form triggered by a
 * card's pencil icon, and - specific to this module - a collapsible profile form for the
 * birth_date/filing_status/annual_income/has_employer_retirement_plan fields that drive
 * every account card's contribution-limit progress bar.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, UserCog } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import RetirementAccountCard from '../components/RetirementAccountCard'
import RetirementAccountForm from '../components/RetirementAccountForm'
import ProfileForm from '../components/ProfileForm'
import {
  useRetirementAccounts,
  useCreateRetirementAccount,
  useUpdateRetirementAccount,
  useDeleteRetirementAccount,
  useMyProfile,
  useUpdateMyProfile,
} from '../hooks/useRetirementAccounts'
import { getApiErrorMessage } from '@/lib/utils'
import type { RetirementAccount, VestingType } from '@/types'

export default function RetirementAccountsPage() {
  const navigate = useNavigate()
  const [showForm, setShowForm] = useState(false)
  const [editingAccount, setEditingAccount] = useState<RetirementAccount | null>(null)
  const [showProfileForm, setShowProfileForm] = useState(false)

  const { data: accounts, isLoading } = useRetirementAccounts()
  const createAccount = useCreateRetirementAccount()
  const updateAccount = useUpdateRetirementAccount()
  const deleteAccount = useDeleteRetirementAccount()
  const { data: profile } = useMyProfile()
  const updateProfile = useUpdateMyProfile()

  // Submit the create-account form, then jump straight to the new account's growth chart.
  const handleCreate = async (data: Parameters<typeof createAccount.mutate>[0]) => {
    try {
      const account = await createAccount.mutateAsync(data)
      setShowForm(false)
      navigate(`/retirement/${account.id}`)
    } catch {
      // handled via createAccount.error
    }
  }

  const handleEditClick = (account: RetirementAccount) => {
    setShowForm(false)
    setEditingAccount(account)
  }

  // account_type is intentionally not forwarded - RetirementAccountUpdate doesn't accept
  // it (locked after creation), even though the shared form still emits it.
  const handleUpdate = async (data: {
    account_name: string
    balance: number
    expected_return_rate: number
    employer_name?: string
    annual_salary?: number
    employer_match_percent?: number
    employer_match_limit_percent?: number
    vesting_type?: VestingType
    vesting_years?: number
  }) => {
    if (!editingAccount) return
    try {
      await updateAccount.mutateAsync({
        id: editingAccount.id,
        data: {
          account_name: data.account_name,
          balance: data.balance,
          expected_return_rate: data.expected_return_rate,
          employer_name: data.employer_name,
          annual_salary: data.annual_salary,
          employer_match_percent: data.employer_match_percent,
          employer_match_limit_percent: data.employer_match_limit_percent,
          vesting_type: data.vesting_type,
          vesting_years: data.vesting_years,
        },
      })
      setEditingAccount(null)
    } catch {
      // handled via updateAccount.error
    }
  }

  const handleUpdateProfile = async (data: Parameters<typeof updateProfile.mutate>[0]) => {
    await updateProfile.mutateAsync(data)
    setShowProfileForm(false)
  }

  const handleDelete = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this account?')) {
      await deleteAccount.mutateAsync(id)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-500">Loading accounts...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Retirement Accounts</h1>
          <p className="text-slate-500">
            Track 401(k), IRA, and HSA balances against 2026 IRS contribution limits
          </p>
        </div>

        <div className="flex gap-3">
          <Button variant="outline" onClick={() => setShowProfileForm((v) => !v)}>
            <UserCog className="h-4 w-4 mr-2" />
            Profile
          </Button>
          <Button
            onClick={() => {
              setEditingAccount(null)
              setShowForm(true)
            }}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Account
          </Button>
        </div>
      </div>

      {showProfileForm && (
        <Card>
          <CardHeader>
            <CardTitle>Your Profile</CardTitle>
          </CardHeader>
          <CardContent>
            <ProfileForm
              profile={profile}
              onSubmit={handleUpdateProfile}
              isLoading={updateProfile.isPending}
              onCancel={() => setShowProfileForm(false)}
            />
          </CardContent>
        </Card>
      )}

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>Create New Account</CardTitle>
          </CardHeader>
          <CardContent>
            {createAccount.isError && (
              <div className="mb-4 rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
                {getApiErrorMessage(createAccount.error, 'Failed to create account')}
              </div>
            )}
            <RetirementAccountForm
              onSubmit={handleCreate}
              isLoading={createAccount.isPending}
              onCancel={() => setShowForm(false)}
            />
          </CardContent>
        </Card>
      )}

      {editingAccount && (
        <Card>
          <CardHeader>
            <CardTitle>Edit Account</CardTitle>
          </CardHeader>
          <CardContent>
            {updateAccount.isError && (
              <div className="mb-4 rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
                {getApiErrorMessage(updateAccount.error, 'Failed to update account')}
              </div>
            )}
            <RetirementAccountForm
              account={editingAccount}
              onSubmit={handleUpdate}
              isLoading={updateAccount.isPending}
              onCancel={() => setEditingAccount(null)}
            />
          </CardContent>
        </Card>
      )}

      {accounts?.length === 0 && !showForm ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-slate-500 mb-4">No retirement accounts yet</p>
            <Button onClick={() => setShowForm(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Your First Account
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="flex gap-6 overflow-x-auto pb-2">
          {accounts?.map((account) => (
            <div key={account.id} className="w-80 flex-shrink-0">
              <RetirementAccountCard account={account} onDelete={handleDelete} onEdit={handleEditClick} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
