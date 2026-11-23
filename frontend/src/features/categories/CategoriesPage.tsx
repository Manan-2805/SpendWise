import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Plus } from 'lucide-react'
import { Field, Message, TextField } from '@/components/fields'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { api, unwrap } from '@/lib/api/client'
import type { Category } from '@/lib/api/client'
import { ApiError } from '@/lib/api/transport'
import { showFormError } from '@/lib/forms'
import { invalidateFinance, useCategories } from './queries'

const schema = z.object({
  name: z.string().trim().min(1, 'Enter a category name.').max(100),
  type: z.enum(['income', 'expense', 'both']),
  color: z.string().trim().refine(value => value === '' || /^#[\da-f]{6}$/i.test(value), 'Use a six-digit hex color such as #446688.'),
  icon: z.string().trim().max(50),
  description: z.string().trim().max(500),
})

function Editor({ category, close }: { category?: Category; close: () => void }) {
  const { register, handleSubmit, setError, formState: { errors, dirtyFields } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { name: category?.name ?? '', type: category?.type ?? 'expense', color: category?.color ?? '', icon: category?.icon ?? '', description: category?.description ?? '' },
  })
  const edit = useMutation({
    mutationFn: async (value: z.infer<typeof schema>) => {
      const body = { ...value, color: value.color || null, icon: value.icon || null, description: value.description || null }
      if (!category) return unwrap(await api.POST('/api/v1/categories/', { body }))
      return unwrap(await api.PATCH('/api/v1/categories/{category_id}', {
        params: { path: { category_id: category.id } },
        body: Object.fromEntries(Object.entries(body).filter(([key]) => key in dirtyFields)),
      }))
    },
    onSuccess: async () => {
      close()
      toast.success(category ? 'Category saved' : 'Category created')
      await invalidateFinance(true)
    },
    onError: error => showFormError(error, setError, ['name', 'type', 'color', 'icon', 'description']),
  })
  return <form className="stack p-4" noValidate onSubmit={handleSubmit(data => edit.mutateAsync(data).catch(() => {}))}>
    <TextField id="category-name" label="Name" autoComplete="off" error={errors.name?.message} {...register('name')} />
    <Field id="category-type" label="Type" error={errors.type?.message}>
      <select id="category-type" aria-invalid={errors.type ? true : undefined} {...register('type')}>
        <option value="expense">Expense</option><option value="income">Income</option><option value="both">Both</option>
      </select>
    </Field>
    <TextField id="category-description" label="Description (optional)" autoComplete="off" error={errors.description?.message} {...register('description')} />
    <div className="form-grid">
      <TextField id="category-color" label="Hex color (optional)" autoComplete="off" error={errors.color?.message} {...register('color')} />
      <TextField id="category-icon" label="Icon or emoji (optional)" autoComplete="off" error={errors.icon?.message} {...register('icon')} />
    </div>
    {errors.root?.message && <Message error>{errors.root.message}</Message>}
    <div className="inline-actions"><Button type="submit" disabled={edit.isPending}>{category ? 'Save category' : 'Create category'}</Button>
      <Button type="button" variant="outline" onClick={close}>Cancel</Button></div>
  </form>
}

function DeleteCategory({ category, categories, close }: { category: Category; categories: Category[]; close: () => void }) {
  const [target, setTarget] = useState('')
  const remove = useMutation({
    mutationFn: async () => unwrap(await api.DELETE('/api/v1/categories/{category_id}', {
      params: { path: { category_id: category.id }, query: target ? { reassign_to_id: Number(target) } : {} },
    })),
    onSuccess: async () => {
      close()
      toast.success('Category deleted')
      await invalidateFinance(true)
    },
  })
  const conflict = remove.error instanceof ApiError && remove.error.status === 409
  const options = categories.filter(item => item.id !== category.id && (item.type === 'both' || category.type === 'both' || item.type === category.type))
  return <form className="stack" onSubmit={event => { event.preventDefault(); remove.mutate() }}>
    {remove.isError && <Message error>{remove.error.message}</Message>}
    {conflict && <Field id="reassign" label="Move existing transactions to">
      <select id="reassign" required value={target} onChange={event => setTarget(event.target.value)}>
        <option value="">Choose another category</option>
        {options.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    </Field>}
    <div className="inline-actions"><Button variant="destructive" type="submit" disabled={remove.isPending || (conflict && !target)}>Delete category</Button>
      <Button type="button" variant="outline" onClick={close}>Cancel</Button></div>
  </form>
}

export default function CategoriesPage() {
  const categories = useCategories()
  const [editor, setEditor] = useState<Category | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Category | null>(null)
  const opener = useRef<HTMLButtonElement>(null)
  function restoreFocus(event: Event) {
    event.preventDefault()
    if (opener.current?.isConnected) opener.current.focus()
    else document.querySelector<HTMLButtonElement>('#add-category')?.focus()
  }
  return <>
    <div className="page-heading">
      <div><p>Organize your ledger</p><h1>Categories</h1></div>
      <Button id="add-category" onClick={event => { opener.current = event.currentTarget; setEditor('new') }}><Plus aria-hidden="true" />Add category</Button>
    </div>
    {categories.isPending ? <p role="status">Loading categories…</p> : categories.isError ?
      <Message error>{categories.error.message} <Button variant="outline" onClick={() => void categories.refetch()}>Try again</Button></Message> :
      categories.data.length === 0 ? <Message>No categories yet. Add one to organize your transactions.</Message> :
      <ul className="form-grid" aria-label="Categories">
        {categories.data.map(category => <li key={category.id} className="surface stack">
          <div><h2>{category.name}</h2><p className="muted">{category.type === 'both' ? 'Income and expense' : category.type === 'income' ? 'Income' : 'Expense'}{category.user_id === null ? ' · System category' : ''}</p></div>
          {category.description && <p>{category.description}</p>}
          {category.user_id !== null && <div className="inline-actions">
            <Button variant="outline" aria-label={`Edit ${category.name}`} onClick={event => { opener.current = event.currentTarget; setEditor(category) }}>Edit</Button>
            <Button variant="ghost" aria-label={`Delete ${category.name}`} onClick={event => { opener.current = event.currentTarget; setDeleting(category) }}>Delete</Button>
          </div>}
        </li>)}
      </ul>}
    <Sheet open={editor !== null} onOpenChange={open => { if (!open) setEditor(null) }}>
      <SheetContent className="sheet-scroll w-full sm:max-w-lg" onCloseAutoFocus={restoreFocus}>
        <SheetHeader><SheetTitle>{editor === 'new' ? 'Add category' : 'Edit category'}</SheetTitle>
          <SheetDescription>Choose how transactions are grouped in your reports.</SheetDescription></SheetHeader>
        {editor && <Editor key={editor === 'new' ? 'new' : editor.id} category={editor === 'new' ? undefined : editor} close={() => setEditor(null)} />}
      </SheetContent>
    </Sheet>
    <Dialog open={deleting !== null} onOpenChange={open => { if (!open) setDeleting(null) }}>
      <DialogContent className="dialog-scroll" onCloseAutoFocus={restoreFocus}>
        <DialogHeader><DialogTitle>Delete category?</DialogTitle><DialogDescription>{deleting?.name} will be removed from your categories.</DialogDescription></DialogHeader>
        {deleting && <DeleteCategory category={deleting} categories={categories.data ?? []} close={() => setDeleting(null)} />}
      </DialogContent>
    </Dialog>
  </>
}
