import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Message, TextField } from '@/components/fields'
import { api, discardSessionBody, unwrap } from '@/lib/api/client'
import { showFormError } from '@/lib/forms'
import { queryClient, sessionKey } from '@/app/query'
import { email, loginSchema, registerSchema, resetSchema } from './schema'
import { loadSignedInUser } from './session'

function GuestPage({ title, text, children }: { title: string; text: string; children: ReactNode }) {
  return <div className="auth-grid">
    <div className="auth-intro">
      <p>Your personal ledger</p><h1>{title}</h1><p>{text}</p>
    </div>
    <section className="surface stack auth-form" aria-label={title}>{children}</section>
  </div>
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const state: unknown = location.state
  const suggested = state && typeof state === 'object' && 'email' in state && typeof state.email === 'string' ? state.email : ''
  const notice = state && typeof state === 'object' && 'notice' in state && typeof state.notice === 'string' ? state.notice : undefined
  const { register, handleSubmit, setError, formState: { errors } } = useForm({
    resolver: zodResolver(loginSchema), defaultValues: { email: suggested, password: '' },
  })
  const login = useMutation({ mutationFn: async (body: z.infer<typeof loginSchema>) => {
    await discardSessionBody(await api.POST('/api/v1/auth/login', { body, parseAs: 'stream' }))
    await loadSignedInUser()
  }, onSuccess: () => { void navigate('/', { replace: true }) },
  onError: error => showFormError(error, setError, ['email', 'password']) })

  return <GuestPage title="Sign in" text="See what came in, what went out, and where you stand.">
    {notice && <Message>{notice}</Message>}
    <form className="stack" noValidate onSubmit={handleSubmit(data => login.mutateAsync(data).catch(() => {}))}>
      <TextField id="login-email" label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register('email')} />
      <TextField id="login-password" label="Password" type="password" autoComplete="current-password" error={errors.password?.message} {...register('password')} />
      {errors.root?.message && <Message error>{errors.root.message}</Message>}
      <Button type="submit" disabled={login.isPending}>{login.isPending ? 'Signing in…' : 'Sign in'}</Button>
    </form>
    <Link to="/forgot-password" className="sw-link">Forgot password?</Link>
    <p>New to SpendWise? <Link className="sw-link" to="/register">Create an account</Link></p>
  </GuestPage>
}

export function RegisterPage() {
  const navigate = useNavigate()
  const { register, handleSubmit, setError, formState: { errors } } = useForm({
    resolver: zodResolver(registerSchema),
  })
  const mutation = useMutation({ mutationFn: async (body: z.infer<typeof registerSchema>) => {
    await discardSessionBody(await api.POST('/api/v1/auth/register', { body, parseAs: 'stream' }))
    await loadSignedInUser()
  }, onSuccess: () => { void navigate('/', { replace: true }) },
  onError: error => showFormError(error, setError, ['email', 'username', 'password', 'confirm_password'], 'confirm_password') })
  return <GuestPage title="Create an account" text="Start a personal ledger for your everyday spending.">
    <form className="stack" noValidate onSubmit={handleSubmit(data => mutation.mutateAsync(data).catch(() => {}))}>
      <TextField id="register-email" label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register('email')} />
      <TextField id="register-username" label="Username" autoComplete="username" error={errors.username?.message} {...register('username')} />
      <TextField id="register-password" label="Password" type="password" autoComplete="new-password" error={errors.password?.message} {...register('password')} />
      <TextField id="register-confirm" label="Confirm password" type="password" autoComplete="new-password" error={errors.confirm_password?.message} {...register('confirm_password')} />
      {errors.root?.message && <Message error>{errors.root.message}</Message>}
      <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Creating account…' : 'Create account'}</Button>
    </form>
    <p>Already registered? <Link className="sw-link" to="/login">Sign in</Link></p>
  </GuestPage>
}

const forgotSchema = z.object({ email })

export function ForgotPage() {
  const { register, handleSubmit, setError, formState: { errors } } = useForm({ resolver: zodResolver(forgotSchema) })
  const reminder = useMutation({
    mutationFn: async (body: z.infer<typeof forgotSchema>) => unwrap(await api.POST('/api/v1/auth/forgot-password', { body })),
    onError: error => showFormError(error, setError, ['email']),
  })
  return <GuestPage title="Forgot password" text="Request a link to choose a new password.">
    {reminder.isSuccess ? <Message>{reminder.data.message}</Message> :
      <form className="stack" noValidate onSubmit={handleSubmit(data => reminder.mutateAsync(data).catch(() => {}))}>
        <TextField id="forgot-email" label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register('email')} />
        {errors.root?.message && <Message error>{errors.root.message}</Message>}
        <Button type="submit" disabled={reminder.isPending}>{reminder.isPending ? 'Sending link…' : 'Send reset link'}</Button>
      </form>}
    <Link className="sw-link" to="/login">Back to sign in</Link>
  </GuestPage>
}

function useEmailToken() {
  const [params, setParams] = useSearchParams()
  const [token] = useState(() => params.get('token'))
  useEffect(() => {
    if (params.has('token')) {
      const next = new URLSearchParams(params)
      next.delete('token')
      void setParams(next, { replace: true })
    }
  }, [params, setParams])
  return token
}

export function ResetPage() {
  const token = useEmailToken()
  const { register, handleSubmit, setError, formState: { errors } } = useForm({ resolver: zodResolver(resetSchema) })
  const reset = useMutation({
    mutationFn: async (values: z.infer<typeof resetSchema>) => {
      if (!token) throw new Error('Open the password reset link from your email.')
      return unwrap(await api.POST('/api/v1/auth/reset-password', { body: { ...values, token } }))
    },
    onError: error => showFormError(error, setError, ['new_password', 'confirm_new_password'], 'confirm_new_password'),
  })
  return <GuestPage title="Reset password" text="Choose a password for your SpendWise account.">
    {reset.isSuccess ? <Message>{reset.data.message}</Message> : token ?
      <form className="stack" noValidate onSubmit={handleSubmit(data => reset.mutateAsync(data).catch(() => {}))}>
        <TextField id="reset-password" label="New password" type="password" autoComplete="new-password" error={errors.new_password?.message} {...register('new_password')} />
        <TextField id="reset-confirm" label="Confirm new password" type="password" autoComplete="new-password" error={errors.confirm_new_password?.message} {...register('confirm_new_password')} />
        {errors.root?.message && <Message error>{errors.root.message}</Message>}
        <Button type="submit" disabled={reset.isPending}>{reset.isPending ? 'Saving password…' : 'Reset password'}</Button>
      </form> : <Message error>Open the reset link from your email, or request a new link.</Message>}
    {reset.isSuccess ? <Link className="sw-link" to="/login">Sign in</Link> :
      <Link className="sw-link" to="/forgot-password">Request a new link</Link>}
  </GuestPage>
}

export function VerifyPage() {
  const token = useEmailToken()
  const verify = useMutation({
    mutationFn: async () => {
      if (!token) throw new Error('Open the verification link from your email.')
      return unwrap(await api.GET('/api/v1/auth/verify-email', { params: { query: { token } } }))
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: sessionKey }),
  })
  return <GuestPage title="Verify email" text="Confirm the email address attached to your account.">
    {verify.isSuccess ? <Message>{verify.data.message}</Message> :
      token ? <Button type="button" disabled={verify.isPending} onClick={() => verify.mutate()}>
        {verify.isPending ? 'Verifying…' : 'Verify email'}
      </Button> : <Message error>Open the verification link from your email to continue.</Message>}
    {verify.isError && <Message error>{verify.error.message}</Message>}
    <Link className="sw-link" to="/">Go to SpendWise</Link>
  </GuestPage>
}
