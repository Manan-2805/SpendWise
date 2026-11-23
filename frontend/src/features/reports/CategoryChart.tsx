import { useMemo } from 'react'
import { Bar, BarChart, XAxis, YAxis } from 'recharts'
import { ChartContainer } from '@/components/ui/chart'
import { formatAmount } from '@/lib/amount'
import type { CategoryShare } from './queries'

const chartConfig = { share: { label: 'Share', color: 'var(--focus)' } }

export function CategoryChart({ entries }: { entries: CategoryShare[] }) {
  const plot = useMemo(() => entries.slice(0, 8).map(entry => ({
    category: entry.category_name,
    share: entry.percentage,
  })), [entries])

  return <div className="stack">
    <div aria-hidden="true">
      <ChartContainer config={chartConfig} className="aspect-auto min-h-36 w-full" style={{ height: Math.max(144, plot.length * 33) }}>
        <BarChart accessibilityLayer={false} layout="vertical" data={plot} margin={{ right: 12, left: 4 }}>
          <XAxis type="number" domain={[0, 100]} hide />
          <YAxis type="category" dataKey="category" tickLine={false} axisLine={false} width={97} tickMargin={5} />
          <Bar dataKey="share" fill="var(--color-share)" radius={4} maxBarSize={16} isAnimationActive={false} />
        </BarChart>
      </ChartContainer>
    </div>
    {entries.length > plot.length && <p className="muted">Chart shows the first eight categories.</p>}
    <table className="w-full" aria-label="Category report data">
      <thead><tr><th className="text-left" scope="col">Category</th><th className="text-right" scope="col">Amount</th><th className="text-right" scope="col">Share</th></tr></thead>
      <tbody>{entries.map(entry => <tr className="border-t border-border" key={entry.category_id ?? 'uncategorized'}>
        <th className="py-2 text-left font-medium" scope="row">{entry.category_name}</th>
        <td className="numbers text-right">{formatAmount(entry.total)}</td>
        <td className="numbers text-right">{new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(entry.percentage)}%</td>
      </tr>)}</tbody>
    </table>
  </div>
}
