import { z } from 'zod'

export const email = z.string().trim().toLowerCase().pipe(z.email({ error: 'Enter a valid email address.' }))
export const username = z.string().trim().toLowerCase()
  .regex(/^[a-z0-9_-]{3,50}$/, 'Use 3–50 letters, numbers, dashes or underscores.')
const withinBcryptLimit = (value: string) => new TextEncoder().encode(value).length <= 72
export const password = z.string().min(1, 'Enter a password.')
  .refine(withinBcryptLimit, 'Use at most 72 UTF-8 bytes.')
export const newPassword = z.string()
  .min(8, 'Use at least 8 characters.')
  .regex(/[A-Z]/, 'Add an uppercase letter.')
  .regex(/[a-z]/, 'Add a lowercase letter.')
  .regex(/\d/, 'Add a number.')
  .refine(withinBcryptLimit, 'Use at most 72 UTF-8 bytes.')

export const loginSchema = z.object({ email, password })
export const registerSchema = z.object({ email, username, password: newPassword, confirm_password: z.string() })
  .refine(values => values.password === values.confirm_password, { error: 'Passwords must match.', path: ['confirm_password'] })
export const resetSchema = z.object({ new_password: newPassword, confirm_new_password: z.string() })
  .refine(values => values.new_password === values.confirm_new_password, { error: 'Passwords must match.', path: ['confirm_new_password'] })
