import { Pencil, Trash2 } from 'lucide-react'
import type { Category, Transaction } from '@/lib/api/client'
import { formatAmount } from '@/lib/amount'
import { displayDate } from '@/lib/dates'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'

export function TransactionTable({ items, categories, actions }: {
  items: Transaction[]
  categories: Category[]
  actions?: (item: Transaction, action: 'edit' | 'delete', opener: HTMLButtonElement) => void
}) {
  const names = new Map(categories.map(item => [item.id, item.name]))
  return <div className="min-w-0 overflow-x-auto" tabIndex={0} role="region" aria-label="Transaction table">
    <Table className="transaction-table">
      <TableHeader><TableRow>
        <TableHead scope="col">Description</TableHead><TableHead scope="col" className="transaction-detail">Category</TableHead>
        <TableHead scope="col" className="transaction-detail">Date</TableHead><TableHead scope="col" className="amount-cell">Amount</TableHead>
        {actions && <TableHead scope="col">Actions</TableHead>}
      </TableRow></TableHeader>
      <TableBody>{items.map(item => {
        const label = item.description ?? 'Untitled transaction'
        const sign = item.type === 'income' ? '+' : '−'
        const type = item.type === 'income' ? 'Income' : 'Expense'
        const category = item.category?.name ?? (item.category_id === null ? 'Uncategorized' : names.get(item.category_id) ?? 'Category unavailable')
        const date = displayDate(item.transaction_date)
        return <TableRow key={item.id}>
          <TableCell className="transaction-label font-semibold">
            {label}
            <span className="transaction-meta muted">{category} · {date}</span>
          </TableCell>
          <TableCell className="transaction-detail">{category}</TableCell>
          <TableCell className="transaction-detail">{date}</TableCell>
          <TableCell className={`amount-cell numbers ${item.type}`}><span className="sr-only">{type} </span>{sign}{formatAmount(item.amount)}</TableCell>
          {actions && <TableCell><div className="transaction-actions">
            <Button variant="ghost" size="icon" aria-label={`Edit ${label}`} onClick={event => actions(item, 'edit', event.currentTarget)}><Pencil aria-hidden="true" /></Button>
            <Button variant="ghost" size="icon" aria-label={`Delete ${label}`} onClick={event => actions(item, 'delete', event.currentTarget)}><Trash2 aria-hidden="true" /></Button>
          </div></TableCell>}
        </TableRow>
      })}</TableBody>
    </Table>
  </div>
}
