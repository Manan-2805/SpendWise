import { useMutation } from '@tanstack/react-query'
import { api, unwrap } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { Message } from '@/components/fields'

export function VerificationNotice() {
  const resend = useMutation({ mutationFn: async () => unwrap(await api.POST('/api/v1/auth/resend-verification')) })
  return <aside className="surface stack" aria-label="Email verification">
    <div><h2>Verify your email</h2><p className="muted">Use the link sent to your account email to verify it.</p></div>
    <div><Button variant="outline" disabled={resend.isPending} onClick={() => resend.mutate()}>
      {resend.isPending ? 'Sending…' : 'Resend verification'}
    </Button></div>
    {resend.isSuccess && <Message>{resend.data.message}</Message>}
    {resend.isError && <Message error>{resend.error.message}</Message>}
  </aside>
}
