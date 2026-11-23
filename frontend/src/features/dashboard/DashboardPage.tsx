import { Link, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowDownLeft, ArrowUpRight, Plus, Wallet } from 'lucide-react'
import { Field, Message } from '@/components/fields'
import { Button } from '@/components/ui/button'
import { api, unwrap } from '@/lib/api/client'
import { formatAmount } from '@/lib/amount'
import { today } from '@/lib/dates'
import { useSession } from '@/features/auth/session'
import { VerificationNotice } from '@/features/auth/VerificationNotice'
import { useCategories } from '@/features/categories/queries'
import { TransactionTable } from '@/features/transactions/TransactionTable'
import { useCategoryBreakdown, useMonthlySummary } from '@/features/reports/queries'
import { CategoryChart } from '@/features/reports/CategoryChart'

export default function DashboardPage() {
  const [params, setParams] = useSearchParams()
  const requested = params.get('month') ?? ''
  const month = /^(19\d{2}|20\d{2}|2100)-(0[1-9]|1[0-2])$/.test(requested) ? requested : today().slice(0, 7)
  const type = params.get('movement') === 'income' ? 'income' : 'expense'
  const session = useSession()
  const summary = useMonthlySummary(month)
  const breakdown = useCategoryBreakdown(month, type)
  const categories = useCategories()
  const recent = useQuery({
    queryKey: ['transactions', 'recent'],
    queryFn: async ({ signal }) => unwrap(await api.GET('/api/v1/transactions/', {
      signal, params: { query: { page: 1, per_page: 5, sort_by: 'created_at', sort_order: 'desc' } },
    })),
  })
  return <div className="stack">
    <div className="page-heading">
      <div><p>{session.data ? `Ledger for ${session.data.username}` : 'Your ledger'}</p><h1>A month in view</h1></div>
      <Button asChild><Link to="/transactions?new=1"><Plus aria-hidden="true" />Add transaction</Link></Button>
    </div>
    <div className="flex flex-wrap items-end justify-between gap-3">
      <Field id="report-month" label="Report month">
        <input id="report-month" type="month" value={month} min="1900-01" max="2100-12" onChange={event => {
          if (!event.target.value) return
          const next = new URLSearchParams(params)
          next.set('month', event.target.value)
          void setParams(next)
        }} />
      </Field>
    </div>
    {summary.isPending ? <p role="status">Loading monthly summary…</p> : summary.isError ?
      <Message error>{summary.error.message} <Button variant="outline" onClick={() => void summary.refetch()}>Try again</Button></Message> :
      <dl className="metrics" aria-label="Monthly summary">
        <div className="surface kpi"><dt className="flex items-center gap-2"><Wallet size={18} aria-hidden="true" />Balance</dt><dd><strong className="numbers">{formatAmount(summary.data.balance)}</strong></dd></div>
        <div className="surface kpi"><dt className="flex items-center gap-2"><ArrowDownLeft size={18} aria-hidden="true" />Income</dt><dd><strong className="income numbers">+{formatAmount(summary.data.income)}</strong></dd></div>
        <div className="surface kpi"><dt className="flex items-center gap-2"><ArrowUpRight size={18} aria-hidden="true" />Expenses</dt><dd><strong className="expense numbers">−{formatAmount(summary.data.expense)}</strong></dd></div>
      </dl>}
    <div className="dashboard-grid">
      <section className="surface stack" aria-labelledby="category-report">
        <h2 id="category-report">Category report</h2>
        <Field id="report-type" label="Show">
          <select id="report-type" value={type} onChange={event => {
            const next = new URLSearchParams(params)
            if (event.target.value === 'income') next.set('movement', 'income')
            else next.delete('movement')
            void setParams(next)
          }}><option value="expense">Expenses</option><option value="income">Income</option></select>
        </Field>
        {breakdown.isPending ? <p role="status">Loading categories…</p> : breakdown.isError ?
          <Message error>{breakdown.error.message} <Button variant="outline" onClick={() => void breakdown.refetch()}>Try again</Button></Message> :
          breakdown.data.length ? <CategoryChart entries={breakdown.data} /> : <p className="muted">No category activity for this month.</p>}
      </section>
      <section className="surface stack" aria-labelledby="recent">
        <h2 id="recent">Recent transactions</h2>
        {recent.isPending ? <p role="status">Loading recent activity…</p> : recent.isError ?
          <Message error>{recent.error.message} <Button variant="outline" onClick={() => void recent.refetch()}>Try again</Button></Message> :
          recent.data.items.length ? <TransactionTable items={recent.data.items} categories={categories.data ?? []} /> : <p className="muted">Add a transaction to see it here.</p>}
        <Link className="sw-link" to="/transactions">View all transactions</Link>
      </section>
    </div>
    {session.data && !session.data.is_verified && <VerificationNotice />}
  </div>
}
