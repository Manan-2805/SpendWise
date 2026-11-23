import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from 'next-themes'
import { Toaster } from './components/ui/sonner'
import { queryClient } from './app/query'
import { AppRouter } from './app/router'
import './styles.css'

const root = document.getElementById('root')
if (!root) throw new Error('SpendWise cannot find its application root.')

createRoot(root).render(<StrictMode>
  <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
    <QueryClientProvider client={queryClient}>
      <AppRouter />
      <Toaster />
    </QueryClientProvider>
  </ThemeProvider>
</StrictMode>)
