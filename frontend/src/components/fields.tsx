import { useState, type ComponentProps, type ReactNode } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { Input } from './ui/input'
import { Button } from './ui/button'

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

type TextFieldProps = ComponentProps<typeof Input> & {
  id: string
  label: string
  error?: string
}

export function TextField({ id, label, error, ...props }: TextFieldProps) {
  return <Field id={id} label={label} error={error}>
    <Input {...props} id={id} aria-invalid={error ? true : undefined} aria-describedby={error ? id + '-error' : undefined} />
  </Field>
}

export function PasswordField({ id, label, error, ...props }: Omit<TextFieldProps, 'type'>) {
  const [visible, setVisible] = useState(false)
  return <Field id={id} label={label} error={error}>
    <div className="password-control">
      <Input {...props} id={id} type={visible ? 'text' : 'password'} spellCheck={false}
        aria-invalid={error ? true : undefined} aria-describedby={error ? id + '-error' : undefined} />
      <Button type="button" variant="ghost" size="icon"
        aria-label={`${visible ? 'Hide' : 'Show'} ${label.toLowerCase()}`}
        aria-controls={id} onClick={() => setVisible(value => !value)}>
        {visible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
      </Button>
    </div>
  </Field>
}

export function Message({ children, error = false, tone = 'info' }: {
  children: ReactNode
  error?: boolean
  tone?: 'info' | 'success' | 'warning'
}) {
  return <div className="message" data-tone={error ? 'error' : tone} role={error ? 'alert' : 'status'}>{children}</div>
}
