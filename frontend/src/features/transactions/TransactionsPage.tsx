import { useRef, useState } from 'react'
import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Field, Message, TextField } from '@/components/fields'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { api, unwrap } from '@/lib/api/client'
import type { Category, Transaction } from '@/lib/api/client'
import { useCategories, invalidateFinance } from '@/features/categories/queries'
import { filterNames, rangeError, readFilters } from './filters'
import { TransactionEditor } from './TransactionEditor'
import { TransactionTable } from './TransactionTable'

function Filters({ params, categories, apply }: {
  params: URLSearchParams
  categories: Category[]
  apply: (params: URLSearchParams) => void
}) {
  const [error, setError] = useState<string>()
  return <form className="surface stack" aria-label="Filter transactions" onSubmit={event => {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    const next = new URLSearchParams()
    for (const key of filterNames) {
      const value = values.get(key)
      if (typeof value === 'string' && value.trim()) next.set(key, value.trim())
    }
    const problem = rangeError(next)
    setError(problem)
    if (!problem) apply(next)
  }}>
    <div className="form-grid">
      <TextField id="search" label="Search descriptions" name="search" type="search" defaultValue={params.get('search') ?? ''} maxLength={100} />
      <Field id="filter-category" label="Category"><select id="filter-category" name="category_id" defaultValue={params.get('category_id') ?? ''}>
        <option value="">All categories</option>{categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
      </select></Field>
      <Field id="filter-type" label="Type"><select id="filter-type" name="type" defaultValue={params.get('type') ?? ''}>
        <option value="">All types</option><option value="income">Income</option><option value="expense">Expense</option>
      </select></Field>
      <Field id="sort" label="Sort by"><select id="sort" name="sort_by" defaultValue={params.get('sort_by') ?? 'transaction_date'}>
        <option value="transaction_date">Transaction date</option><option value="created_at">Recently added</option><option value="amount">Amount</option>
      </select></Field>
    </div>
    <details open={['date_from', 'date_to', 'min_amount', 'max_amount', 'sort_order'].some(key => params.has(key))}>
      <summary className="cursor-pointer font-semibold">Dates, amounts and sort order</summary>
      <div className="form-grid pt-3">
        <TextField id="from" label="Start date" name="date_from" type="date" defaultValue={params.get('date_from') ?? ''} />
        <TextField id="to" label="End date" name="date_to" type="date" defaultValue={params.get('date_to') ?? ''} />
        <TextField id="min" label="Minimum amount" name="min_amount" inputMode="decimal" defaultValue={params.get('min_amount') ?? ''} />
        <TextField id="max" label="Maximum amount" name="max_amount" inputMode="decimal" defaultValue={params.get('max_amount') ?? ''} />
        <Field id="sort-order" label="Order"><select id="sort-order" name="sort_order" defaultValue={params.get('sort_order') ?? 'desc'}>
          <option value="desc">Descending</option><option value="asc">Ascending</option>
        </select></Field>
      </div>
    </details>
    {(error ?? rangeError(params)) && <Message error>{error ?? rangeError(params)}</Message>}
    <div className="inline-actions">
      <Button type="submit">Apply filters</Button>
      <Button type="reset" variant="ghost" onClick={() => { setError(undefined); apply(new URLSearchParams()) }}>Clear filters</Button>
    </div>
  </form>
}

export default function TransactionsPage() {
  const [params, setParams] = useSearchParams()
  const [editor, setEditor] = useState<number | 'new' | null>(params.get('new') === '1' ? 'new' : null)
  const [deleting, setDeleting] = useState<Transaction | null>(null)
  const opener = useRef<HTMLButtonElement>(null)
  const categories = useCategories()
  const filters = readFilters(params)
  const list = useQuery({
    queryKey: ['transactions', 'list', filters],
    queryFn: async ({ signal }) => unwrap(await api.GET('/api/v1/transactions/', { signal, params: { query: filters } })),
    placeholderData: keepPreviousData,
  })
  function changePage(page: number) {
    const next = new URLSearchParams(params)
    if (page === 1) next.delete('page')
    else next.set('page', String(page))
    void setParams(next)
  }
  function closeEditor() {
    setEditor(null)
    if (params.has('new')) {
      const next = new URLSearchParams(params)
      next.delete('new')
      void setParams(next, { replace: true })
    }
  }
  function restoreFocus(event: Event) {
    event.preventDefault()
    if (opener.current?.isConnected) opener.current.focus()
    else document.querySelector<HTMLButtonElement>('#add-transaction')?.focus()
  }
  const remove = useMutation({
    mutationFn: async (id: number) => unwrap(await api.DELETE('/api/v1/transactions/{transaction_id}', { params: { path: { transaction_id: id } } })),
    onSuccess: async () => {
      setDeleting(null)
      if (list.data?.items.length === 1 && (filters.page ?? 1) > 1) changePage((filters.page ?? 1) - 1)
      toast.success('Transaction deleted')
      await invalidateFinance()
    },
  })
  return <div className="stack">
    <div className="page-heading">
      <div><p>Your ledger</p><h1>Transactions</h1></div>
      <Button id="add-transaction" onClick={event => { opener.current = event.currentTarget; setEditor('new') }}><Plus aria-hidden="true" />Add transaction</Button>
    </div>
    <Filters params={params} key={params.toString()} categories={categories.data ?? []} apply={next => void setParams(next)} />
    <section className="surface stack" aria-label="Transaction results">
      {list.isPending ? <p role="status">Loading transactions…</p> : list.isError ?
        <Message error>{list.error.message} <Button variant="outline" onClick={() => void list.refetch()}>Try again</Button></Message> :
        <>
          {list.data.items.length ? <TransactionTable items={list.data.items} categories={categories.data ?? []} actions={(item, action, button) => {
            opener.current = button
            if (action === 'edit') setEditor(item.id)
            else { remove.reset(); setDeleting(item) }
          }} /> : <p className="muted">No transactions match these filters.</p>}
          <nav className="inline-actions" aria-label="Transaction pagination">
            <Button variant="outline" disabled={!list.data.has_prev || list.isPlaceholderData} onClick={() => changePage(list.data.page - 1)}>Previous</Button>
            <span role="status" className="muted">{list.data.pages ? `Page ${list.data.page} of ${list.data.pages} · ${list.data.total} total` : '0 results'}</span>
            <Button variant="outline" disabled={!list.data.has_next || list.isPlaceholderData} onClick={() => changePage(list.data.page + 1)}>Next</Button>
          </nav>
        </>}
    </section>
    <Sheet open={editor !== null} onOpenChange={open => { if (!open) closeEditor() }}>
      <SheetContent className="sheet-scroll w-full sm:max-w-lg" onCloseAutoFocus={restoreFocus}>
        <SheetHeader><SheetTitle>{editor === 'new' ? 'Add transaction' : 'Edit transaction'}</SheetTitle>
          <SheetDescription>Record a movement in your ledger.</SheetDescription></SheetHeader>
        {editor !== null && <TransactionEditor id={editor} key={editor} close={closeEditor} />}
      </SheetContent>
    </Sheet>
    <Dialog open={deleting !== null} onOpenChange={open => { if (!open) setDeleting(null) }}>
      <DialogContent className="dialog-scroll" onCloseAutoFocus={restoreFocus}>
        <DialogHeader><DialogTitle>Delete transaction?</DialogTitle>
          <DialogDescription>{deleting?.description ?? 'This transaction'} will be removed from your ledger and reports.</DialogDescription></DialogHeader>
        {remove.isError && <Message error>{remove.error.message}</Message>}
        <div className="inline-actions">
          <Button variant="destructive" disabled={remove.isPending} onClick={() => { if (deleting) remove.mutate(deleting.id) }}>Delete transaction</Button>
          <Button variant="outline" onClick={() => setDeleting(null)}>Cancel</Button>
        </div>
      </DialogContent>
    </Dialog>
  </div>
}
