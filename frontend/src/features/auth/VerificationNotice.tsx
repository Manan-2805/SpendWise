import { useMutation } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { Message } from '@/components/fields'

export function VerificationNotice() {
  const resend = useMutation({ mutationFn: async () => unwrap(await api.POST('/api/v1/auth/resend-verification')) })
  return <aside className="surface stack verification-notice" aria-label="Email verification">
    <div><h2>Verify your email</h2><p className="muted">Check your inbox or request a fresh verification link.</p></div>
    <div><Button variant="outline" disabled={resend.isPending} onClick={() => resend.mutate()}>
      {resend.isPending ? 'Sending…' : 'Send verification email'}
    </Button></div>
    {resend.isSuccess && <Message tone="success">{resend.data.message}</Message>}
    {resend.isError && <Message error>{resend.error.message}</Message>}
  </aside>
}
