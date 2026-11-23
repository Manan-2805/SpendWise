import { Suspense } from 'react'
import type { ReactNode } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTheme } from 'next-themes'
import { Moon, Sun } from 'lucide-react'
import { Link, NavLink, Navigate, Outlet, useNavigate } from 'react-router'
import { Brand } from './Brand'
import { clearAccount } from './query'
import { Button } from '@/components/ui/button'
import { Message } from '@/components/fields'
import { useSession } from '@/features/auth/session'
import { api, unwrap } from '@/lib/api/client'

function Header({ children }: { children?: ReactNode }) {
  const { resolvedTheme, setTheme } = useTheme()
  const dark = resolvedTheme === 'dark'
  return <>
    <a href="#main-content" className="skip-link">Skip to content</a>
    <header className="app-header glass-surface">
      <div className="wrap nav-inner">
        <Brand />
        {children}
        <Button type="button" variant="ghost" size="icon" aria-label={dark ? 'Use light theme' : 'Use dark theme'}
          onClick={() => setTheme(dark ? 'light' : 'dark')}>
          {dark ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
        </Button>
      </div>
    </header>
  </>
}

function Content({ children }: { children?: ReactNode }) {
  return <main className="wrap app-main" id="main-content" tabIndex={-1}>
    <Suspense fallback={<p role="status">Loading page…</p>}>{children ?? <Outlet />}</Suspense>
  </main>
}

export function GuestLayout() {
  return <><Header /><Content /></>
}

export function WorkspaceLayout() {
  const session = useSession()
  const navigate = useNavigate()
  const logout = useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/v1/auth/logout')),
    onSuccess: () => {
      clearAccount()
      void navigate('/login', { replace: true })
    },
  })
  if (session.isPending) return <><Header /><Content><p role="status">Loading your workspace…</p></Content></>
  if (session.isError) return <><Header /><Content>
    <Message error>{session.error.message}</Message>
    <Button variant="outline" onClick={() => void session.refetch()}>Try again</Button>
    <Link className="sw-link" to="/login">Sign in</Link>
  </Content></>
  if (!session.data) return <Navigate to="/login" replace />

  return <>
    <Header>
      <nav className="main-links" aria-label="Main navigation">
        <NavLink to="/" end>Overview</NavLink>
        <NavLink to="/transactions">Transactions</NavLink>
        <NavLink to="/categories">Categories</NavLink>
        <NavLink to="/profile">Profile</NavLink>
        <Button variant="ghost" type="button" onClick={() => logout.mutate()} disabled={logout.isPending}>
          {logout.isPending ? 'Signing out…' : 'Sign out'}
        </Button>
      </nav>
    </Header>
    <Content>
      {logout.isError && <Message error>{logout.error.message}</Message>}
      <Outlet />
    </Content>
  </>
}

export function NotFound() {
  return <div className="surface stack"><h1>Page not found</h1><Link className="sw-link" to="/">Go to overview</Link></div>
}

export function RouteError() {
  return <><Header /><Content>
    <div className="surface stack"><h1>Could not load this page</h1>
      <p>Try reloading, or return to your overview.</p><Link className="sw-link" to="/">Go to overview</Link></div>
  </Content></>
}
