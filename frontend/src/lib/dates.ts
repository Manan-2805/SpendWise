export function today() {
  return new Date().toISOString().slice(0, 10)
}

export function isDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const date = new Date(value + 'T00:00:00Z')
  return Number.isFinite(date.valueOf()) && date.toISOString().startsWith(value)
}

export function displayDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' })
    .format(new Date(value + 'T00:00:00Z'))
}

export function monthBounds(month: string) {
  const [year, number] = month.split('-').map(Number)
  const start = month + '-01'
  const end = new Date(Date.UTC(year, number, 0)).toISOString().slice(0, 10)
  return { year, month: number, date_from: start, date_to: end }
}
