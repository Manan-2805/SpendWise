import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { clearAccount, queryClient, sessionKey } from '@/app/query'
import { TextField, Message } from '@/components/fields'
import { Button } from '@/components/ui/button'
import { api, unwrap } from '@/lib/api/client'
import type { User } from '@/lib/api/client'
import { showFormError } from '@/lib/forms'
import { email, username, password, newPassword } from '@/features/auth/schema'
import { VerificationNotice } from '@/features/auth/VerificationNotice'

const profileKey = ['profile'] as const
const userSchema = z.object({ email, username })
const passwordSchema = z.object({ current_password: password, new_password: newPassword, confirm_new_password: z.string() })
  .refine(values => values.new_password === values.confirm_new_password, { error: 'Passwords must match.', path: ['confirm_new_password'] })

function UserDetails({ user }: { user: User }) {
  const navigate = useNavigate()
  const { register, handleSubmit, setError, formState: { errors, isDirty } } = useForm({
    resolver: zodResolver(userSchema), defaultValues: { email: user.email, username: user.username },
  })
  const update = useMutation({
    mutationFn: async (values: z.infer<typeof userSchema>) => unwrap(await api.PATCH('/api/v1/users/me', {
      body: {
        ...(values.email !== user.email ? { email: values.email } : {}),
        ...(values.username !== user.username ? { username: values.username } : {}),
      },
    })),
    onSuccess: updated => {
      if (updated.email !== user.email) {
        void navigate('/login', { replace: true, state: { email: updated.email, notice: 'Email updated. Sign in and request a new verification email.' } })
        clearAccount()
      } else {
        queryClient.setQueryData(profileKey, updated)
        queryClient.setQueryData(sessionKey, updated)
        toast.success('Profile saved')
      }
    },
    onError: error => showFormError(error, setError, ['email', 'username']),
  })
  return <section className="surface stack">
    <h2>Account details</h2>
    <form className="stack" noValidate onSubmit={handleSubmit(data => update.mutateAsync(data).catch(() => {}))}>
      <TextField id="profile-user" label="Username" autoComplete="username" error={errors.username?.message} {...register('username')} />
      <TextField id="profile-email" label="Email" type="email" autoComplete="email" error={errors.email?.message} {...register('email')} />
      <p className="muted">Changing your email signs you out. You can verify the new address after signing back in.</p>
      {errors.root?.message && <Message error>{errors.root.message}</Message>}
      <div><Button disabled={update.isPending || !isDirty} type="submit">Save profile</Button></div>
    </form>
  </section>
}

function ChangePassword() {
  const navigate = useNavigate()
  const { register, handleSubmit, setError, formState: { errors } } = useForm({ resolver: zodResolver(passwordSchema) })
  const change = useMutation({
    mutationFn: async (body: z.infer<typeof passwordSchema>) => unwrap(await api.POST('/api/v1/auth/change-password', { body })),
    onSuccess: () => {
      void navigate('/login', { replace: true, state: { notice: 'Password changed. Sign in with your new password.' } })
      clearAccount()
    },
    onError: error => showFormError(error, setError, ['current_password', 'new_password', 'confirm_new_password'], 'confirm_new_password'),
  })
  return <section className="surface stack">
    <h2>Change password</h2>
    <form className="stack" noValidate onSubmit={handleSubmit(data => change.mutateAsync(data).catch(() => {}))}>
      <TextField id="old-password" label="Current password" type="password" autoComplete="current-password" error={errors.current_password?.message} {...register('current_password')} />
      <TextField id="new-password" label="New password" type="password" autoComplete="new-password" error={errors.new_password?.message} {...register('new_password')} />
      <TextField id="confirm-new-password" label="Confirm new password" type="password" autoComplete="new-password" error={errors.confirm_new_password?.message} {...register('confirm_new_password')} />
      {errors.root?.message && <Message error>{errors.root.message}</Message>}
      <div><Button disabled={change.isPending} type="submit">Change password</Button></div>
    </form>
  </section>
}

export default function ProfilePage() {
  const user = useQuery({ queryKey: profileKey, queryFn: async ({ signal }) => unwrap(await api.GET('/api/v1/users/me', { signal })) })
  return <div className="stack">
    <h1>Profile</h1>
    {user.isPending ? <p role="status">Loading profile…</p> : user.isError ?
      <Message error>{user.error.message} <Button variant="outline" onClick={() => void user.refetch()}>Try again</Button></Message> :
      <>
        {!user.data.is_verified && <VerificationNotice />}
        <div className="form-grid">
          <UserDetails key={user.data.username + ':' + user.data.email} user={user.data} />
          <ChangePassword />
        </div>
      </>}
  </div>
}
