import { useRef, useState, type CSSProperties } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Folder, Pencil, Plus, Search, Trash2, Upload } from 'lucide-react'
import { Field, Message, TextField } from '@/components/fields'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { api, unwrap } from '@/lib/api/client'
import type { Category } from '@/lib/api/client'
import { ApiError } from '@/lib/api/transport'
import { showFormError } from '@/lib/forms'
import { invalidateFinance, useCategories } from './queries'
import { categoryIconPath, compactCategoryIcon } from './categoryIcon'

const schema = z.object({
  name: z.string().trim().min(1, 'Enter a category name.').max(100),
  type: z.enum(['income', 'expense', 'both']),
  color: z.string().trim().refine(value => value === '' || /^#[\da-f]{6}$/i.test(value), 'Use a six-digit hex color such as #446688.'),
  icon: z.string().trim().max(50),
  description: z.string().trim().max(500),
})

const typeLabels = { expense: 'Expense', income: 'Income', both: 'Income and expense' }

function CategoryMark({ icon, color }: { icon?: string | null; color?: string | null }) {
  const path = icon ? categoryIconPath(icon) : null
  return <span className="category-mark" aria-hidden="true" style={{ '--category-color': color || undefined } as CSSProperties}>
    {path ? <svg viewBox="0 0 16 16"><path d={path} /></svg> :
      icon && [...icon].length <= 4 ? icon : <Folder size={17} />}
  </span>
}

function Editor({ category, close }: { category?: Category; close: () => void }) {
  const { register, control, handleSubmit, setValue, setError, clearErrors, formState: { errors, dirtyFields } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { name: category?.name ?? '', type: category?.type ?? 'expense', color: category?.color ?? '', icon: category?.icon ?? '', description: category?.description ?? '' },
  })
  const [color, icon] = useWatch({ control, name: ['color', 'icon'] })
  const [uploading, setUploading] = useState(false)
  async function upload(file: File) {
    setUploading(true)
    try {
      setValue('icon', await compactCategoryIcon(file), { shouldDirty: true })
      clearErrors('icon')
    } catch (error) {
      setError('icon', { message: error instanceof Error ? error.message : 'Could not read the image.' })
    } finally {
      setUploading(false)
    }
  }
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
    <div className="category-appearance">
      <CategoryMark color={color} icon={icon} />
      <div className="stack">
        <Field id="category-color" label="Category color" error={errors.color?.message}>
          <div className="inline-actions">
            <input id="category-color" type="color" value={color || '#286699'}
              onInput={event => setValue('color', event.currentTarget.value, { shouldDirty: true })} />
            {color && <Button type="button" variant="ghost" onClick={() => setValue('color', '', { shouldDirty: true })}>Clear color</Button>}
          </div>
        </Field>
        <Field id="category-icon-file" label="Upload icon image" error={errors.icon?.message}>
          <div className="category-upload">
            <Upload size={17} aria-hidden="true" />
            <input id="category-icon-file" type="file" accept="image/png,image/jpeg,image/webp"
              aria-describedby={errors.icon ? 'category-icon-hint category-icon-file-error' : 'category-icon-hint'}
              aria-invalid={errors.icon ? true : undefined} disabled={uploading}
              onChange={event => { const file = event.currentTarget.files?.[0]; if (file) void upload(file); event.currentTarget.value = '' }} />
          </div>
        </Field>
        <p id="category-icon-hint" className="muted">PNG, JPEG, or WebP. Saved as a small monochrome icon.</p>
        {!categoryIconPath(icon) && <TextField id="category-icon" label="Emoji or icon name" autoComplete="off" {...register('icon')} />}
        {icon && <Button type="button" variant="ghost" onClick={() => { setValue('icon', '', { shouldDirty: true }); clearErrors('icon') }}>Remove icon</Button>}
      </div>
    </div>
    {errors.root?.message && <Message error>{errors.root.message}</Message>}
    <div className="inline-actions"><Button type="submit" disabled={edit.isPending || uploading}>{category ? 'Save category' : 'Create category'}</Button>
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
    {remove.isError && <Message error={!conflict} tone="warning">{remove.error.message}</Message>}
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
  const [search, setSearch] = useState('')
  const [type, setType] = useState('')
  const opener = useRef<HTMLButtonElement>(null)
  const term = search.trim().toLowerCase()
  const visibleCategories = categories.data?.filter(category =>
    (!type || category.type === type) &&
    [category.name, category.description ?? ''].some(value => value.toLowerCase().includes(term))
  ) ?? []
  function restoreFocus(event: Event) {
    event.preventDefault()
    if (opener.current?.isConnected) opener.current.focus()
    else document.querySelector<HTMLButtonElement>('#add-category')?.focus()
  }
  return <>
    <div className="page-heading">
      <h1>Categories</h1>
      <Button id="add-category" onClick={event => { opener.current = event.currentTarget; setEditor('new') }}><Plus aria-hidden="true" />Add category</Button>
    </div>
    {categories.isPending ? <p role="status">Loading categories…</p> : categories.isError ?
      <Message error>{categories.error.message} <Button variant="outline" onClick={() => void categories.refetch()}>Try again</Button></Message> :
      categories.data.length === 0 ? <Message>No categories yet. Add one to organize your transactions.</Message> :
      <section className="surface stack category-panel">
        <div className="category-toolbar">
          <div className="category-search"><Search size={18} aria-hidden="true" />
            <input className="form-control" aria-label="Search categories" type="search" placeholder="Search categories" value={search} onChange={event => setSearch(event.target.value)} />
          </div>
          <select className="form-control category-filter" aria-label="Filter by category type" value={type} onChange={event => setType(event.target.value)}>
            <option value="">All types</option><option value="expense">Expense</option>
            <option value="income">Income</option><option value="both">Income and expense</option>
          </select>
        </div>
        <Table aria-label="Categories" className="category-table">
          <TableHeader><TableRow>
            <TableHead scope="col">Category</TableHead><TableHead scope="col">Type</TableHead><TableHead scope="col">Actions</TableHead>
          </TableRow></TableHeader>
          <TableBody>{visibleCategories.map(category => <TableRow key={category.id}>
            <TableCell><div className="category-title">
              <CategoryMark icon={category.icon} color={category.color} />
              <div><strong>{category.name}</strong>
                {category.description && <p className="muted">{category.description}</p>}
              </div>
            </div></TableCell>
            <TableCell><span className="category-type" data-type={category.type}>{typeLabels[category.type]}</span></TableCell>
            <TableCell>{category.user_id === null ? <span className="muted">System category</span> : <div className="category-actions">
              <Button variant="ghost" size="icon" aria-label={`Edit ${category.name}`} onClick={event => { opener.current = event.currentTarget; setEditor(category) }}><Pencil aria-hidden="true" /></Button>
              <Button variant="ghost" size="icon" aria-label={`Delete ${category.name}`} onClick={event => { opener.current = event.currentTarget; setDeleting(category) }}><Trash2 aria-hidden="true" /></Button>
            </div>}</TableCell>
          </TableRow>)}</TableBody>
        </Table>
        {!visibleCategories.length && <Message>No categories match these filters.</Message>}
      </section>}
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
