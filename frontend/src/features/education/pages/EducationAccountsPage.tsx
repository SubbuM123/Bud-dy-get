/**
 * List view for the Education Savings module, mounted at /education. Mirrors
 * RetirementAccountsPage's structure: every account as a horizontally-scrollable strip of
 * cards, an inline "create account" form, and an inline "edit account" form triggered by a
 * card's pencil icon. No profile form here, unlike retirement's - 529s have no
 * income/age-based eligibility, so there's nothing profile-level to configure.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import EducationAccountCard from '../components/EducationAccountCard'
import EducationAccountForm from '../components/EducationAccountForm'
import {
  useEducationAccounts,
  useCreateEducationAccount,
  useUpdateEducationAccount,
  useDeleteEducationAccount,
} from '../hooks/useEducationAccounts'
import { getApiErrorMessage } from '@/lib/utils'
import type { EducationAccount } from '@/types'

export default function EducationAccountsPage() {
  const navigate = useNavigate()
  const [showForm, setShowForm] = useState(false)
  const [editingAccount, setEditingAccount] = useState<EducationAccount | null>(null)

  const { data: accounts, isLoading } = useEducationAccounts()
  const createAccount = useCreateEducationAccount()
  const updateAccount = useUpdateEducationAccount()
  const deleteAccount = useDeleteEducationAccount()

  // Submit the create-account form, then jump straight to the new account's growth chart.
  const handleCreate = async (data: Parameters<typeof createAccount.mutate>[0]) => {
    try {
      const account = await createAccount.mutateAsync(data)
      setShowForm(false)
      navigate(`/education/${account.id}`)
    } catch {
      // handled via createAccount.error
    }
  }

  const handleEditClick = (account: EducationAccount) => {
    setShowForm(false)
    setEditingAccount(account)
  }

  // account_type is intentionally not forwarded - EducationAccountUpdate doesn't accept
  // it (locked after creation), even though the shared form still emits it.
  const handleUpdate = async (data: {
    account_name: string
    beneficiary_name: string
    beneficiary_birth_date?: string
    plan_provider?: string
    balance: number
    expected_return_rate: number
  }) => {
    if (!editingAccount) return
    try {
      await updateAccount.mutateAsync({
        id: editingAccount.id,
        data: {
          account_name: data.account_name,
          beneficiary_name: data.beneficiary_name,
          beneficiary_birth_date: data.beneficiary_birth_date,
          plan_provider: data.plan_provider,
          balance: data.balance,
          expected_return_rate: data.expected_return_rate,
        },
      })
      setEditingAccount(null)
    } catch {
      // handled via updateAccount.error
    }
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
          <h1 className="text-2xl font-bold text-slate-900">Education Savings</h1>
          <p className="text-slate-500">
            Track 529 college savings plans and 2026 gift-tax guidance per beneficiary
          </p>
        </div>

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
            <EducationAccountForm
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
            <EducationAccountForm
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
            <p className="text-slate-500 mb-4">No education savings accounts yet</p>
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
              <EducationAccountCard account={account} onDelete={handleDelete} onEdit={handleEditClick} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
