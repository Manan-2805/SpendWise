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
    <Table>
      <TableHeader><TableRow>
        <TableHead scope="col">Description</TableHead><TableHead scope="col">Category</TableHead>
        <TableHead scope="col">Date</TableHead><TableHead scope="col" className="amount-cell">Amount</TableHead>
        {actions && <TableHead scope="col">Actions</TableHead>}
      </TableRow></TableHeader>
      <TableBody>{items.map(item => {
        const label = item.description ?? 'Untitled transaction'
        const sign = item.type === 'income' ? '+' : '−'
        const type = item.type === 'income' ? 'Income' : 'Expense'
        return <TableRow key={item.id}>
          <TableCell className="font-semibold">{label}</TableCell>
          <TableCell>{item.category?.name ?? (item.category_id === null ? 'Uncategorized' : names.get(item.category_id) ?? 'Category unavailable')}</TableCell>
          <TableCell>{displayDate(item.transaction_date)}</TableCell>
          <TableCell className={`amount-cell numbers ${item.type}`}><span className="sr-only">{type} </span>{sign}{formatAmount(item.amount)}</TableCell>
          {actions && <TableCell><div className="inline-actions">
            <Button variant="ghost" aria-label={`Edit ${label}`} onClick={event => actions(item, 'edit', event.currentTarget)}>Edit</Button>
            <Button variant="ghost" aria-label={`Delete ${label}`} onClick={event => actions(item, 'delete', event.currentTarget)}>Delete</Button>
          </div></TableCell>}
        </TableRow>
      })}</TableBody>
    </Table>
  </div>
}
