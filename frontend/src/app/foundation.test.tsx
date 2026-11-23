import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { server } from '../../vite.config'
import { Brand } from './Brand'

describe('frontend foundation', () => {
  it('renders the SpendWise brand as a home link', () => {
    render(<Brand />)
    expect(screen.getByRole('link', { name: 'SpendWise' })).toHaveAttribute('href', '/')
  })

  it('preserves the browser Host and never chooses a different port', () => {
    expect(server).toMatchObject({
      port: 3000,
      strictPort: true,
      proxy: { '/api/v1': { target: 'http://127.0.0.1:8000', changeOrigin: false } },
    })
  })
})
