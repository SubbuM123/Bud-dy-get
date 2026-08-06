/**
 * List view for the Income module, mounted at /income. The entry point for the money-flow
 * reform's "salary flows to destinations via percentage allocation" model (see
 * docs/plan.md): every income the user has defined, each showing its allocation split by
 * destination account name, an inline create form, and a "Log Paycheck" action per
 * recurring income that posts real Transaction rows and bumps real account balances - see
 * hooks/useIncome.ts.
 */
import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import IncomeCard from '../components/IncomeCard'
import IncomeForm from '../components/IncomeForm'
import LogIncomeModal from '../components/LogIncomeModal'
import { useIncomes, useCreateIncome, useDeleteIncome, useLogIncome } from '../hooks/useIncome'
import { useBankAccounts } from '@/features/bank-accounts/hooks/useBankAccounts'
import { useRetirementAccounts } from '@/features/retirement/hooks/useRetirementAccounts'
import { useEducationAccounts } from '@/features/education/hooks/useEducationAccounts'
import { getApiErrorMessage } from '@/lib/utils'
import type { Income } from '@/types'

export default function IncomePage() {
  const [showForm, setShowForm] = useState(false)
  const [loggingIncome, setLoggingIncome] = useState<Income | null>(null)

  const { data: incomes, isLoading } = useIncomes()
  const { data: bankAccounts } = useBankAccounts()
  const { data: retirementAccounts } = useRetirementAccounts()
  const { data: educationAccounts } = useEducationAccounts()

  const createIncome = useCreateIncome()
  const deleteIncome = useDeleteIncome()
  const logIncome = useLogIncome()

  const destinationNames = new Map<string, string>()
  ;(bankAccounts ?? []).forEach((a) => destinationNames.set(a.id, `${a.account_name} (Bank)`))
  ;(retirementAccounts ?? []).forEach((a) => destinationNames.set(a.id, `${a.account_name} (Retirement)`))
  ;(educationAccounts ?? []).forEach((a) => destinationNames.set(a.id, `${a.account_name} (Education)`))

  const handleCreate = async (data: Parameters<typeof createIncome.mutate>[0]) => {
    try {
      await createIncome.mutateAsync(data)
      setShowForm(false)
    } catch {
      // handled via createIncome.error
    }
  }

  const handleDelete = (id: string) => {
    if (window.confirm('Delete this income? Past logged transactions will be kept.')) {
      deleteIncome.mutate(id)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-500">Loading income...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Income</h1>
          <p className="text-slate-500">
            Salary and other income sources, split by percentage across your accounts
          </p>
        </div>

        <Button onClick={() => setShowForm(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Income
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>Add Income</CardTitle>
          </CardHeader>
          <CardContent>
            {createIncome.isError && (
              <div className="mb-4 rounded-md bg-danger-500/10 p-3 text-sm text-danger-500">
                {getApiErrorMessage(createIncome.error, 'Failed to create income')}
              </div>
            )}
            <IncomeForm
              onSubmit={handleCreate}
              isLoading={createIncome.isPending}
              onCancel={() => setShowForm(false)}
            />
          </CardContent>
        </Card>
      )}

      {incomes?.length === 0 && !showForm ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-slate-500 mb-4">No income sources yet</p>
            <Button onClick={() => setShowForm(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Your First Income
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {incomes?.map((income) => (
            <IncomeCard
              key={income.id}
              income={income}
              destinationNames={destinationNames}
              onLog={setLoggingIncome}
              onDelete={handleDelete}
              isLogging={logIncome.isPending}
            />
          ))}
        </div>
      )}

      <LogIncomeModal income={loggingIncome} onClose={() => setLoggingIncome(null)} />
    </div>
  )
}
