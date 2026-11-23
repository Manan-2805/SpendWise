import { readFileSync } from 'node:fs'
import { gzipSync } from 'node:zlib'

const dist = new URL('../dist/', import.meta.url)
const manifest = JSON.parse(readFileSync(new URL('.vite/manifest.json', dist), 'utf8'))
const login = 'src/features/auth/AuthPages.tsx'
const dashboard = 'src/features/dashboard/DashboardPage.tsx'

function imports(entries) {
  const found = new Set()
  const pending = [...entries]
  while (pending.length) {
    const key = pending.pop()
    if (found.has(key)) continue
    if (!manifest[key]) throw new Error(`Missing Vite manifest entry ${key}`)
    found.add(key)
    pending.push(...(manifest[key].imports ?? []))
  }
  return found
}

function compressedSize(files) {
  return [...new Set(files)].reduce((sum, file) => sum + gzipSync(readFileSync(new URL(file, dist))).length, 0)
}

const initial = imports(['index.html', login])
if (initial.has(dashboard)) throw new Error('The dashboard is included in the login graph.')
const reports = [...imports([dashboard])].filter(key => !initial.has(key))
const assets = Object.values(manifest).flatMap(item => [...(item.css ?? []), item.file]).filter(file => file.endsWith('.css'))
const budgets = [
  ['Entry and login JS', compressedSize([...initial].map(key => manifest[key].file)), 220],
  ['Lazy report JS', compressedSize(reports.map(key => manifest[key].file)), 160],
  ['CSS', compressedSize(assets), 65],
]

for (const [label, bytes, limit] of budgets) {
  const kib = bytes / 1024
  console.log(`${label}: ${kib.toFixed(2)} KiB gzip (budget ${limit} KiB)`)
  if (kib > limit) process.exitCode = 1
}
