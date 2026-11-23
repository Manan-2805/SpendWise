import { useMutation, useQuery } from '@tanstack/react-query'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { toast } from 'sonner'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Field, Message, TextField } from '@/components/fields'
import { api, unwrap } from '@/lib/api/client'
import type { Category, Transaction } from '@/lib/api/client'
import { validAmount } from '@/lib/amount'
import { isDate, today } from '@/lib/dates'
import { showFormError } from '@/lib/forms'
import { invalidateFinance, useCategories } from '@/features/categories/queries'

const entry = z.object({
  description: z.string().trim().max(500, 'Use at most 500 characters.'),
  amount: z.string().trim().refine(validAmount, 'Enter a positive amount with up to two decimal places.'),
  transaction_date: z.string().refine(isDate, 'Enter a valid date.'),
  category_id: z.string().regex(/^\d*$/, 'Choose a category.'),
  type: z.enum(['expense', 'income']),
  notes: z.string().trim().max(1000, 'Use at most 1,000 characters.'),
  tags: z.string(),
})
type Entry = z.infer<typeof entry>
type Movement = Entry['type']
const splitTags = (value: string) => [...new Set(value.split(',').map(tag => tag.trim().toLowerCase()).filter(Boolean))]

function EntryForm({ item, categories, initialType, close }: {
  item?: Transaction
  categories: Category[]
  initialType: Movement
  close: () => void
}) {
  const schema = entry.superRefine((value, context) => {
    if (!value.description && (!item || item.description !== null)) context.addIssue({ code: 'custom', path: ['description'], message: 'Enter a description.' })
    if (!item && !value.category_id) context.addIssue({ code: 'custom', path: ['category_id'], message: 'Choose a category.' })
    const category = categories.find(option => String(option.id) === value.category_id)
    if (category && category.type !== 'both' && category.type !== value.type) context.addIssue({ code: 'custom', path: ['category_id'], message: 'Choose a category for this transaction type.' })
    const tags = splitTags(value.tags)
    if (tags.length > 10 || tags.some(tag => tag.length > 64)) context.addIssue({ code: 'custom', path: ['tags'], message: 'Use up to 10 tags with at most 64 characters each.' })
  })
  const { register, control, handleSubmit, setError, formState: { errors, dirtyFields } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      description: item?.description ?? '', amount: item?.amount ?? '', transaction_date: item?.transaction_date ?? today(),
      type: item?.type ?? initialType, category_id: item?.category_id?.toString() ?? '', notes: item?.notes ?? '', tags: item?.tags?.join(', ') ?? '',
    },
  })
  const movement = useWatch({ control, name: 'type' })
  const categoryValue = useWatch({ control, name: 'category_id' })
  const matches = categories.filter(category => category.type === 'both' || category.type === movement)
  const save = useMutation({
    mutationFn: async (value: Entry) => {
      const props = {
        ...value, category_id: value.category_id ? Number(value.category_id) : null,
        notes: value.notes || null, tags: splitTags(value.tags),
      }
      if (item) {
        const body = Object.fromEntries(Object.entries(props).filter(([key]) => key in dirtyFields))
        return unwrap(await api.PATCH('/api/v1/transactions/{transaction_id}', { params: { path: { transaction_id: item.id } }, body }))
      }
      if (props.category_id === null) throw new Error('Choose a category.')
      return unwrap(await api.POST('/api/v1/transactions/', { body: { ...props, category_id: props.category_id } }))
    },
    onSuccess: async () => {
      close()
      toast.success(item ? 'Transaction saved' : 'Transaction added')
      await invalidateFinance()
    },
    onError: error => showFormError(error, setError, ['description', 'amount', 'transaction_date', 'category_id', 'type', 'notes', 'tags']),
  })

  return <form className="stack p-4" noValidate onSubmit={handleSubmit(data => save.mutateAsync(data).catch(() => {}))}>
    <TextField id="entry-description" label="Description" autoComplete="off" error={errors.description?.message} {...register('description')} />
    <div className="form-grid">
      <TextField id="entry-amount" label="Amount" inputMode="decimal" autoComplete="off" error={errors.amount?.message} {...register('amount')} />
      <TextField id="entry-date" label="Date" type="date" autoComplete="off" error={errors.transaction_date?.message} {...register('transaction_date')} />
      <Field id="entry-type" label="Type" error={errors.type?.message}><select id="entry-type" {...register('type')}>
        <option value="expense">Expense</option><option value="income">Income</option>
      </select></Field>
      <Field id="entry-category" label="Category" error={errors.category_id?.message}>
        <select id="entry-category" aria-invalid={errors.category_id ? true : undefined} aria-describedby={errors.category_id ? 'entry-category-error' : undefined} {...register('category_id')}>
          <option value="">{item ? 'Uncategorized' : 'Choose a category'}</option>
          {categoryValue && !matches.some(category => String(category.id) === categoryValue) && <option value={categoryValue}>Current category (unavailable)</option>}
          {matches.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
        </select>
      </Field>
    </div>
    <TextField id="entry-notes" label="Notes (optional)" autoComplete="off" error={errors.notes?.message} {...register('notes')} />
    <TextField id="entry-tags" label="Tags (optional, comma separated)" autoComplete="off" error={errors.tags?.message} {...register('tags')} />
    {!item && !matches.length && <Message>Add a compatible category before saving this transaction.</Message>}
    {errors.root?.message && <Message error>{errors.root.message}</Message>}
    <div className="inline-actions"><Button disabled={save.isPending} type="submit">{save.isPending ? 'Saving…' : item ? 'Save transaction' : 'Add transaction'}</Button>
      <Button type="button" variant="outline" onClick={close}>Cancel</Button></div>
  </form>
}

export function TransactionEditor({ id, close }: { id: number | 'new'; close: () => void }) {
  const categories = useCategories()
  const detail = useQuery({
    queryKey: ['transactions', 'detail', id],
    enabled: id !== 'new',
    queryFn: async ({ signal }) => unwrap(await api.GET('/api/v1/transactions/{transaction_id}', {
      params: { path: { transaction_id: Number(id) } }, signal,
    })),
  })
  if (categories.isError) return <Message error>{categories.error.message} <Button variant="outline" onClick={() => void categories.refetch()}>Try again</Button></Message>
  if (detail.isError) return <Message error>{detail.error.message} <Button variant="outline" onClick={() => void detail.refetch()}>Try again</Button></Message>
  if (categories.isPending || (id !== 'new' && detail.isPending)) return <p className="p-4" role="status">Loading transaction form…</p>
  return <EntryForm item={detail.data} categories={categories.data} initialType="expense" close={close} />
}
