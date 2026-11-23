import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { queryClient } from '@/app/query'
import { LoginPage } from '@/features/auth/AuthPages'
import CategoriesPage from '@/features/categories/CategoriesPage'
import TransactionsPage from '@/features/transactions/TransactionsPage'
import DashboardPage from '@/features/dashboard/DashboardPage'
import ProfilePage from '@/features/profile/ProfilePage'
import type { Category, Transaction, User } from '@/lib/api/client'

const base = 'http://localhost:3000/api/v1'
const server = setupServer()
beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterAll(() => server.close())
afterEach(() => { cleanup(); queryClient.clear(); server.resetHandlers() })

const date = '2026-11-14'
const user: User = {
  id: 7, email: 'ledger@example.com', username: 'ledger', created_at: date, is_active: true, is_verified: true,
}
const category: Category = {
  id: 42, name: 'Studio', type: 'expense', color: null, user_id: 7, created_at: date, updated_at: date,
}
const transaction: Transaction = {
  id: 13, user_id: 7, amount: '24.50', category_id: 42, type: 'expense', description: 'Pens',
  transaction_date: date, created_at: date, updated_at: date, notes: null, tags: [],
}

function show(path: string, element: React.ReactElement) {
  return render(<QueryClientProvider client={queryClient}>
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={path.split('?')[0]} element={element} />
        {path !== '/login' && <Route path="/login" element={<LoginPage />} />}
      </Routes>
    </MemoryRouter>
  </QueryClientProvider>)
}

describe('feature flows', () => {
  it('presents a runtime login field error and keeps the entered email', async () => {
    server.use(http.post(base + '/auth/login', () => HttpResponse.json({
      detail: 'Request validation failed', code: 'VALIDATION_ERROR',
      errors: [{ field: 'email', message: 'Check your email', type: 'value_error' }],
    }, { status: 422 })))
    show('/login', <LoginPage />)
    const input = userEvent.setup()
    await input.type(screen.getByLabelText('Email'), user.email)
    await input.type(screen.getByLabelText('Password'), 'ExamplePass123!')
    await input.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Check your email')).toBeVisible()
    expect(screen.getByLabelText('Email')).toHaveValue(user.email)
  })

  it('creates, edits, and deletes an owned category', async () => {
    let rows: Category[] = [{ ...category, id: 1, name: 'Shared', user_id: null }]
    server.use(
      http.get(base + '/categories/', () => HttpResponse.json(rows)),
      http.post(base + '/categories/', () => {
        rows = [...rows, category]
        return HttpResponse.json(category, { status: 201 })
      }),
      http.patch(base + '/categories/42', () => {
        const edited = { ...category, name: 'Workspace' }
        rows = [rows[0], edited]
        return HttpResponse.json(edited)
      }),
      http.delete(base + '/categories/42', () => {
        rows = [rows[0]]
        return new HttpResponse(null, { status: 204 })
      }),
    )
    show('/categories', <CategoriesPage />)
    const input = userEvent.setup()
    expect(await screen.findByText('Expense · System category')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Delete Shared' })).not.toBeInTheDocument()
    await input.click(screen.getByRole('button', { name: 'Add category' }))
    let dialog = await screen.findByRole('dialog', { name: 'Add category' })
    await input.type(within(dialog).getByLabelText('Name'), 'Studio')
    await input.click(within(dialog).getByRole('button', { name: 'Create category' }))
    await input.click(await screen.findByRole('button', { name: 'Edit Studio' }))
    dialog = await screen.findByRole('dialog', { name: 'Edit category' })
    await input.clear(within(dialog).getByLabelText('Name'))
    await input.type(within(dialog).getByLabelText('Name'), 'Workspace')
    await input.click(within(dialog).getByRole('button', { name: 'Save category' }))
    await input.click(await screen.findByRole('button', { name: 'Delete Workspace' }))
    dialog = await screen.findByRole('dialog', { name: 'Delete category?' })
    await input.click(within(dialog).getByRole('button', { name: 'Delete category' }))
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Workspace' })).not.toBeInTheDocument())
  })

  it('sends transaction decimals as strings and omits unchanged PATCH fields', async () => {
    let rows: Transaction[] = []
    let created: unknown
    let updated: unknown
    server.use(
      http.get(base + '/categories/', () => HttpResponse.json([category])),
      http.get(base + '/transactions/', () => HttpResponse.json({
        items: rows, total: rows.length, page: 1, per_page: 20, pages: rows.length ? 1 : 0, has_next: false, has_prev: false,
      })),
      http.post(base + '/transactions/', async ({ request }) => {
        created = await request.json()
        rows = [transaction]
        return HttpResponse.json(transaction, { status: 201 })
      }),
      http.get(base + '/transactions/13', () => HttpResponse.json(rows[0])),
      http.patch(base + '/transactions/13', async ({ request }) => {
        updated = await request.json()
        rows = [{ ...transaction, description: 'Notebooks' }]
        return HttpResponse.json(rows[0])
      }),
      http.delete(base + '/transactions/13', () => {
        rows = []
        return new HttpResponse(null, { status: 204 })
      }),
    )
    show('/transactions', <TransactionsPage />)
    const input = userEvent.setup()
    await input.click(screen.getByRole('button', { name: 'Add transaction' }))
    let dialog = await screen.findByRole('dialog', { name: 'Add transaction' })
    await input.type(within(dialog).getByLabelText('Description'), 'Pens')
    await input.type(within(dialog).getByLabelText('Amount'), '24.50')
    await input.selectOptions(within(dialog).getByLabelText('Category'), '42')
    await input.click(within(dialog).getByRole('button', { name: 'Add transaction' }))
    await input.click(await screen.findByRole('button', { name: 'Edit Pens' }))
    dialog = await screen.findByRole('dialog', { name: 'Edit transaction' })
    const description = await within(dialog).findByLabelText('Description')
    await input.clear(description)
    await input.type(description, 'Notebooks')
    await input.click(within(dialog).getByRole('button', { name: 'Save transaction' }))
    expect(created).toMatchObject({ amount: '24.50', category_id: 42 })
    await input.click(await screen.findByRole('button', { name: 'Delete Notebooks' }))
    dialog = await screen.findByRole('dialog', { name: 'Delete transaction?' })
    await input.click(within(dialog).getByRole('button', { name: 'Delete transaction' }))
    expect(updated).toEqual({ description: 'Notebooks' })
    expect(await screen.findByText('No transactions match these filters.')).toBeVisible()
  })

  it('loads the requested report month and shows a clear empty category state', async () => {
    server.use(
      http.get(base + '/auth/me', () => HttpResponse.json(user)),
      http.get(base + '/reports/monthly-summary', ({ request }) => {
        expect(new URL(request.url).searchParams.get('month')).toBe('11')
        return HttpResponse.json({ year: 2026, month: 11, income: '0.00', expense: '0.00', balance: '0.00' })
      }),
      http.get(base + '/reports/category-breakdown', () => HttpResponse.json([])),
      http.get(base + '/categories/', () => HttpResponse.json([])),
      http.get(base + '/transactions/', () => HttpResponse.json({ items: [], total: 0, page: 1, per_page: 5, pages: 0, has_next: false, has_prev: false })),
    )
    show('/?month=2026-11', <DashboardPage />)
    expect(await screen.findByText('No category activity for this month.')).toBeVisible()
    expect(await screen.findByText('Add a transaction to see it here.')).toBeVisible()
  })

  it('sends the user back to login after a changed email', async () => {
    server.use(
      http.get(base + '/users/me', () => HttpResponse.json(user)),
      http.patch(base + '/users/me', () => HttpResponse.json({ ...user, email: 'updated@example.com', is_verified: false })),
    )
    show('/profile', <ProfilePage />)
    const input = userEvent.setup()
    const email = await screen.findByLabelText('Email')
    await input.clear(email)
    await input.type(email, 'updated@example.com')
    await input.click(screen.getByRole('button', { name: 'Save profile' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeVisible()
    expect(screen.getByLabelText('Email')).toHaveValue('updated@example.com')
  })
})
