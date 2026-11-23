const positiveDecimal = /^\d+(?:\.\d+)?$/
const money = /^-?\d+(?:\.\d{1,2})?$/

export function validAmount(value: string) {
  return /^\d{1,10}(?:\.\d{1,2})?$/.test(value) && /[1-9]/.test(value)
}

export function validRangeAmount(value: string) {
  return positiveDecimal.test(value) && /[1-9]/.test(value)
}

export function compareAmounts(left: string, right: string) {
  const [leftWhole, leftFraction = ''] = left.split('.')
  const [rightWhole, rightFraction = ''] = right.split('.')
  const fractionLength = Math.max(leftFraction.length, rightFraction.length)
  const a = BigInt(leftWhole + leftFraction.padEnd(fractionLength, '0'))
  const b = BigInt(rightWhole + rightFraction.padEnd(fractionLength, '0'))
  return a < b ? -1 : a > b ? 1 : 0
}

function configuredCurrency() {
  const currency = import.meta.env.VITE_CURRENCY?.trim().toUpperCase()
  if (!currency) return undefined
  if (!Intl.supportedValuesOf('currency').includes(currency)) {
    throw new Error('VITE_CURRENCY must contain a supported ISO currency code.')
  }
  return currency
}

export const currency = configuredCurrency()

export function formatAmount(value: string, code = currency, locale?: string) {
  if (!money.test(value)) return '—'
  const [whole, fraction = ''] = value.split('.')
  const integer = BigInt(whole)
  const formatter = new Intl.NumberFormat(locale, {
    ...(code ? { style: 'currency', currency: code } : {}),
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  const digits = new Intl.NumberFormat(locale, { useGrouping: false })
  const parts = formatter.formatToParts(whole.startsWith('-') && integer === 0n ? -1n : integer)
  const fractionDigits = [...fraction.padEnd(2, '0')].map(digit => digits.format(BigInt(digit))).join('')
  return parts.map(part => {
    if (part.type === 'fraction') return fractionDigits
    if (part.type === 'integer' && integer === 0n) return digits.format(0n)
    return part.value
  }).join('')
}
