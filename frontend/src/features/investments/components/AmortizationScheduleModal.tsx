/**
 * Table view of a bond's straight-line amortization schedule - opened from
 * BondHoldingCard's "View Amortization Schedule" link. One row per coupon period (date,
 * coupon payment, amortization amount, resulting book value) - see
 * services/investment_calculator.calculate_bond_amortization_schedule for the math.
 */
import { Modal } from '@/components/ui/modal'
import { formatCurrency, formatDate } from '@/lib/utils'
import { useBondAmortizationSchedule } from '../hooks/useInvestments'
import type { BondHolding } from '@/types'

interface AmortizationScheduleModalProps {
  bond: BondHolding | null
  onClose: () => void
}

export default function AmortizationScheduleModal({ bond, onClose }: AmortizationScheduleModalProps) {
  const { data, isLoading } = useBondAmortizationSchedule(bond?.id ?? '', !!bond)

  if (!bond) {
    return null
  }

  return (
    <Modal open={!!bond} onClose={onClose} title={`${bond.name}: Amortization Schedule`} className="max-w-2xl">
      {isLoading ? (
        <p className="py-6 text-center text-sm text-slate-500">Loading schedule...</p>
      ) : (
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="py-2 pr-2 font-medium">Date</th>
                <th className="py-2 pr-2 text-right font-medium">Coupon</th>
                <th className="py-2 pr-2 text-right font-medium">Amortization</th>
                <th className="py-2 text-right font-medium">Book Value</th>
              </tr>
            </thead>
            <tbody>
              {(data?.schedule ?? []).map((period, index) => (
                <tr key={index} className="border-b border-slate-100 last:border-0">
                  <td className="py-2 pr-2 text-slate-600">{formatDate(period.period_date)}</td>
                  <td className="py-2 pr-2 text-right">{formatCurrency(period.coupon_payment)}</td>
                  <td className="py-2 pr-2 text-right">{formatCurrency(period.amortization_amount)}</td>
                  <td className="py-2 text-right font-medium">{formatCurrency(period.book_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  )
}
