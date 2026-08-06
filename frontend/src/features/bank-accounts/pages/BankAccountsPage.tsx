/**
 * List view for the Bank Account Simulator module, mounted at /bank-accounts. Shows every
 * account as a horizontally-scrollable strip of cards (so the row stays compact as
 * accounts pile up), an inline "create account" form, an inline "edit account" form
 * triggered by a card's pencil icon, and the combined multi-account growth simulation
 * beneath everything.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import AccountCard from '../components/AccountCard'
import AccountForm from '../components/AccountForm'
import CombinedSimulationSection from '../components/CombinedSimulationSection'
import {
  useBankAccounts,
  useCreateBankAccount,
  useUpdateBankAccount,
  useDeleteBankAccount,
} from '../hooks/useBankAccounts'
import { getApiErrorMessage } from '@/lib/utils'
import type { BankAccount } from '@/types'

export default function BankAccountsPage() {
  const navigate = useNavigate()
  const [showForm, setShowForm] = useState(false)
  const [editingAccount, setEditingAccount] = useState<BankAccount | null>(null)
  const { data: accounts, isLoading } = useBankAccounts()
  const createAccount = useCreateBankAccount()
  const updateAccount = useUpdateBankAccount()
  const deleteAccount = useDeleteBankAccount()

  // Submit the create-account form, then jump straight to the new account's growth chart.
  // On failure, do nothing further here - createAccount.error (rendered below) already
  // surfaces the problem, and the form stays open with the entered data intact.
  const handleCreate = async (data: Parameters<typeof createAccount.mutate>[0]) => {
    try {
      const account = await createAccount.mutateAsync(data)
      setShowForm(false)
      navigate(`/bank-accounts/${account.id}`)
    } catch {
      // handled via createAccount.error
    }
  }

  const handleEditClick = (account: BankAccount) => {
    setShowForm(false)
    setEditingAccount(account)
  }

  // account_type is intentionally not forwarded - BankAccountUpdate doesn't accept it
  // (locked after creation), even though the shared AccountForm still emits it.
  const handleUpdate = async (data: {
    account_name: string
    principal: number
    interest_rate?: number
    compounding_frequency: string
    cd_start_date?: string
    cd_term_months?: number
    cd_auto_renew?: boolean
  }) => {
    if (!editingAccount) return
    try {
      await updateAccount.mutateAsync({
        id: editingAccount.id,
        data: {
          account_name: data.account_name,
          principal: data.principal,
          interest_rate: data.interest_rate,
          compounding_frequency: data.compounding_frequency,
          cd_start_date: data.cd_start_date,
          cd_term_months: data.cd_term_months,
          cd_auto_renew: data.cd_auto_renew,
        },
      })
      setEditingAccount(null)
    } catch {
      // handled via updateAccount.error
    }
  }

  // Confirm before deleting, since this cascades to the account's recurring actions/history.
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
          <h1 className="text-2xl font-bold text-slate-900">Bank Accounts</h1>
          <p className="text-slate-500">
            Simulate and track your savings, checking, and CD accounts
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
            <AccountForm
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
            <AccountForm
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
            <p className="text-slate-500 mb-4">No accounts yet</p>
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
              <AccountCard account={account} onDelete={handleDelete} onEdit={handleEditClick} />
            </div>
          ))}
        </div>
      )}

      <CombinedSimulationSection />
    </div>
  )
}
