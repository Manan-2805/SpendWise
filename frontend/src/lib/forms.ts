import type { FieldPath, FieldValues, UseFormSetError } from 'react-hook-form'
import { ApiError } from './api/transport'

export function showFormError<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly FieldPath<T>[],
  confirmation?: FieldPath<T>,
) {
  let focused = false
  if (error instanceof ApiError) {
    const conflict = error.code === 'EMAIL_ALREADY_REGISTERED' ? 'email'
      : error.code === 'USERNAME_ALREADY_TAKEN' ? 'username' : undefined
    const conflictField = fields.find(field => field === conflict)
    if (conflictField) {
      setError(conflictField, { type: 'server', message: error.message }, { shouldFocus: true })
      return
    }
    for (const issue of error.fields) {
      const field = fields.find(name => name === issue.field)
        ?? (confirmation && /passwords? (do not|must) match/i.test(issue.message) ? confirmation : undefined)
      if (field) {
        setError(field, { type: 'server', message: issue.message }, { shouldFocus: !focused })
        focused = true
      } else {
        setError('root', { message: issue.message })
      }
    }
    if (error.fields.length) return
  }
  setError('root', { message: error instanceof Error ? error.message : 'The request could not be completed.' })
}
