import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'

test('signs in, records an expense and sees it in the report', async ({ page, request }) => {
  const email = 'ledger_demo@example.com'
  const password = 'ExamplePass123!'
  const registration = await request.post('/api/v1/auth/register', {
    data: { email, username: 'ledger_demo', password, confirm_password: password },
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
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'A month in view' })).toBeVisible()
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
  const toast = page.locator('[data-sonner-toast]').filter({ hasText: 'Transaction added' })
  await expect(toast).toBeVisible()
  expect(await toast.evaluate(element => getComputedStyle(element).backdropFilter)).toContain('blur')
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
  if (process.env.SPENDWISE_SCREENSHOTS) {
    const dir = resolve(process.env.SPENDWISE_SCREENSHOTS)
    await page.screenshot({ path: resolve(dir, 'dashboard-dark.png'), fullPage: true, animations: 'disabled' })
    await page.setViewportSize({ width: 390, height: 844 })
    await page.getByRole('link', { name: 'Transactions', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Transactions' })).toBeVisible()
    const dismiss = page.getByRole('button', { name: 'Close toast' })
    if (await dismiss.isVisible()) await dismiss.click()
    await page.screenshot({ path: resolve(dir, 'transactions-mobile.png'), fullPage: true, animations: 'disabled' })
  }
  await page.setViewportSize({ width: 390, height: 844 })
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
