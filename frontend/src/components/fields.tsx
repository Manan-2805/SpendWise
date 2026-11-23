import type { ComponentProps, ReactNode } from 'react'
import { Input } from './ui/input'

export function Field({ id, label, error, children }: {
  id: string
  label: string
  error?: string
  children: ReactNode
}) {
  return <div className="field">
    <label htmlFor={id}>{label}</label>
    {children}
    {error && <p className="field-error" id={id + '-error'} role="alert">{error}</p>}
  </div>
}

export function TextField({ id, label, error, ...props }: ComponentProps<typeof Input> & {
  id: string
  label: string
  error?: string
}) {
  return <Field id={id} label={label} error={error}>
    <Input {...props} id={id} aria-invalid={error ? true : undefined} aria-describedby={error ? id + '-error' : undefined} />
  </Field>
}

export function Message({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return <div className="message" data-error={error} role={error ? 'alert' : 'status'}>{children}</div>
}
