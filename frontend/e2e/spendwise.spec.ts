import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { randomUUID } from 'node:crypto'

test('paints the saved theme while the JavaScript bundle is still loading', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('theme', 'dark'))
  let allowScripts = () => {}
  const scriptsReady = new Promise<void>(resolve => { allowScripts = resolve })
  await page.route('**/*', async route => {
    if (['script', 'stylesheet'].includes(route.request().resourceType())) await scriptsReady
    await route.continue()
  })
  try {
    await page.goto('/login', { waitUntil: 'commit' })
    await expect(page.getByRole('status')).toHaveText('Loading SpendWise…')
    await expect(page.locator('html')).toHaveClass('dark')
    await expect(page.locator('html')).toHaveCSS('background-color', 'rgb(16, 39, 33)')
  } finally {
    allowScripts()
  }
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
})

test('signs in, records an expense and sees it in the report', async ({ page, request }) => {
  const username = `ledger_${randomUUID().slice(0, 8)}`
  const email = `${username}@example.com`
  const password = 'ExamplePass123!'
  const registration = await request.post('/api/v1/auth/register', {
    data: { email, username, password, confirm_password: password },
  })
  expect(registration.status()).toBe(201)
  const category = 'Studio'
  const created = await request.post('/api/v1/categories/', { data: { name: category, type: 'expense' } })
  expect(created.status()).toBe(201)

  async function checkAccessibility() {
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
    expect(result.violations, JSON.stringify(result.violations, null, 2)).toEqual([])
  }

  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  await checkAccessibility()
  if (process.env.SPENDWISE_SCREENSHOTS) {
    const dir = resolve(process.env.SPENDWISE_SCREENSHOTS)
    await mkdir(dir, { recursive: true })
    await page.screenshot({ path: resolve(dir, 'sign-in.png'), fullPage: true, animations: 'disabled' })
  }
  await expect(page.getByLabel('Email')).toHaveAttribute('autocomplete', 'username')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Show password' }).click()
  await expect(page.getByLabel('Password', { exact: true })).toHaveAttribute('type', 'text')
  await page.getByRole('button', { name: 'Hide password' }).click()
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'A month in view' })).toBeVisible()
  await page.getByRole('link', { name: 'Categories', exact: true }).click()
  await page.getByRole('searchbox', { name: 'Search categories' }).fill(category)
  const table = page.getByRole('table', { name: 'Categories' })
  await expect(table.getByRole('row')).toHaveCount(2)
  await page.getByRole('button', { name: 'Edit Studio' }).click()
  const editCategory = page.getByRole('dialog', { name: 'Edit category' })
  await editCategory.getByLabel('Category color').fill('#29785b')
  const iconPng = await page.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 16
    const ctx = canvas.getContext('2d')!
    ctx.fillRect(3, 3, 10, 10)
    return canvas.toDataURL().split(',')[1]
  })
  await editCategory.getByLabel('Upload icon image').setInputFiles({
    name: 'category.png', mimeType: 'image/png', buffer: Buffer.from(iconPng, 'base64'),
  })
  await expect(editCategory.getByRole('button', { name: 'Remove icon' })).toBeVisible()
  await editCategory.getByRole('button', { name: 'Save category' }).click()
  await expect(editCategory).toBeHidden()
  const categorySaved = page.getByRole('listitem').filter({ hasText: 'Category saved' })
  await categorySaved.getByRole('button', { name: 'Close toast' }).click()
  await expect(categorySaved).toBeHidden()
  const categoryId = (await created.json()).id
  await expect.poll(async () => {
    const response = await request.get(`/api/v1/categories/${categoryId}`)
    return (await response.json()).icon
  }).toMatch(/^px:[A-Za-z0-9+/]{43}$/)
  await page.getByRole('searchbox', { name: 'Search categories' }).clear()
  await checkAccessibility()
  if (process.env.SPENDWISE_SCREENSHOTS) {
    await page.screenshot({ path: resolve(process.env.SPENDWISE_SCREENSHOTS, 'categories.png'), fullPage: true, animations: 'disabled' })
  }
  await page.getByRole('link', { name: 'Transactions', exact: true }).click()
  await page.getByRole('button', { name: 'Add transaction' }).focus()
  await page.keyboard.press('Enter')
  const sheet = page.getByRole('dialog', { name: 'Add transaction' })
  await expect(sheet).toBeVisible()
  await expect(sheet.getByLabel('Category').locator('option', { hasText: category })).toBeAttached()
  await checkAccessibility()
  expect(await sheet.evaluate(element => getComputedStyle(element).backdropFilter)).toContain('blur')
  await sheet.getByLabel('Description', { exact: true }).fill('Studio supplies')
  await sheet.getByLabel('Amount', { exact: true }).fill('24.50')
  await sheet.getByLabel('Category', { exact: true }).selectOption({ label: category })
  await sheet.getByRole('button', { name: 'Add transaction', exact: true }).click()
  await expect(page.getByRole('cell', { name: 'Studio supplies', exact: true })).toBeVisible()
  for (const name of ['Previous', 'Next']) {
    const button = page.getByRole('button', { name })
    await expect(button).toBeDisabled()
    await expect(button).toHaveCSS('cursor', 'default')
  }
  const toast = page.locator('[data-sonner-toast]').filter({ hasText: 'Transaction added' })
  await expect(toast).toBeVisible()
  expect(await toast.evaluate(element => getComputedStyle(element).backdropFilter)).toContain('blur')
  await toast.getByRole('button', { name: 'Close toast' }).click()
  await expect(toast).toBeHidden()
  await page.getByRole('link', { name: 'Overview', exact: true }).click()
  const report = page.getByRole('table', { name: 'Category report data' })
  await expect(report.getByRole('row', { name: new RegExp(category) })).toContainText('24.50')
  await checkAccessibility()

  const header = page.locator('.app-header')
  expect(await header.evaluate(element => getComputedStyle(element).backdropFilter)).toContain('blur')
  if (process.env.SPENDWISE_SCREENSHOTS) {
    const dir = resolve(process.env.SPENDWISE_SCREENSHOTS)
    await mkdir(dir, { recursive: true })
    await page.screenshot({ path: resolve(dir, 'dashboard-light.png'), fullPage: true, animations: 'disabled' })
  }
  await page.getByRole('button', { name: 'Use dark theme' }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  expect(await header.evaluate(element => getComputedStyle(element).backdropFilter)).toContain('blur')
  const recentRow = page.getByRole('region', { name: 'Recent transactions' }).getByRole('row', { name: /Studio supplies/ })
  await expect(recentRow).toHaveCSS('transition-property', 'background-color')
  await checkAccessibility()
  const chart = page.getByRole('region', { name: 'Category report' }).locator('[data-slot="chart"]')
  await expect(chart).toHaveCSS('overflow-x', 'clip')
  const screenshots = process.env.SPENDWISE_SCREENSHOTS
  if (screenshots) await page.screenshot({ path: resolve(screenshots, 'dashboard-dark.png'), fullPage: true, animations: 'disabled' })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('link', { name: 'Transactions', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Transactions' })).toBeVisible()
  const amount = page.getByRole('cell', { name: /Expense.*24\.50/ })
  await expect(amount).toBeVisible()
  await expect.poll(async () => {
    const box = await amount.boundingBox()
    return box !== null && box.x >= 0 && box.x + box.width <= 390
  }).toBe(true)
  await page.evaluate(() => window.scrollTo(0, 0))
  if (screenshots) await page.screenshot({ path: resolve(screenshots, 'transactions-mobile.png'), fullPage: true, animations: 'disabled' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect((await header.boundingBox())?.height).toBeLessThan(165)
  await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'active' })
  await expect.poll(() => header.evaluate(element => getComputedStyle(element).backdropFilter)).toBe('none')
  await page.emulateMedia({ forcedColors: 'none' })
  const protocol = await page.context().newCDPSession(page)
  await protocol.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-transparency', value: 'reduce' }],
  })
  await expect.poll(() => header.evaluate(element => getComputedStyle(element).backdropFilter)).toBe('none')
})
