import { describe, expect, it, vi } from 'vitest'
import { collectCategoryPages } from './queries'

describe('category pagination', () => {
  it('loads the final empty page for exact multiples', async () => {
    const load = vi.fn(async (page: number) => page < 3 ? Array.from({ length: 100 }, (_, index) => index + (page - 1) * 100) : [])
    const values = await collectCategoryPages(load)
    expect(values).toHaveLength(200)
    expect(load.mock.calls).toEqual([[1], [2], [3]])
  })

  it('stops after a short page including an empty first page', async () => {
    const load = vi.fn(async () => [])
    expect(await collectCategoryPages(load)).toEqual([])
    expect(load).toHaveBeenCalledOnce()
  })
})
