// Today's pace: cumulative spend as a stepped cyan line with a soft fill, a dashed projection to the end
// of the day, the budget as a flat amber line with red shading from where the projection crosses it,
// Wave starts as x-axis ticks, then the top 4 Workstreams by today's spend with a thin model-split bar.
import type { Repo } from './types'
import { hourTicks, mergeSeries, todayPace } from './usage'

export type { Series } from './usage'

const W = 760, H = 240, L = 48, R = 14, T = 14, B = 26
const usd = (n: number) => `$${n.toFixed(2)}`
const SPLIT = ['var(--fa1)', 'var(--fa2)', 'var(--fa3)', 'var(--fa4)']
const hm = (t: number) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })

export function UsageChart({ repos }: { repos: Repo[] }) {
  const withUsage = repos.flatMap(r => r.workstreams.filter(ws => ws.series).map(ws => ({ r, ws })))
  const series = mergeSeries(withUsage.map(({ ws }) => ws.series))
  if (!series) return <p className="hint">No usage yet. The chart fills in once a worker writes its first session log entry.</p>
  const budgets = repos.flatMap(r => r.workstreams.filter(ws => ws.budgetUsd != null))
  const budget = budgets.length ? budgets.reduce((n, ws) => n + ws.budgetUsd!, 0) : null
  // The crossing comes from the same total spend and projection the chart draws, against the budget line.
  const { start, end, now, spent, projected, cross, steps } = todayPace(series, budget)
  const max = Math.max(projected, budget ?? 0, 1e-6) * 1.08
  const x = (t: number) => L + ((t - start) / (end - start)) * (W - L - R)
  const y = (v: number) => H - B - (v / max) * (H - T - B)
  const line = `M${x(start)},${y(0)} L${x(steps[0]?.from ?? now).toFixed(1)},${y(0)} ${steps.map(s => `L${x(s.from).toFixed(1)},${y(s.v).toFixed(1)} L${x(s.to).toFixed(1)},${y(s.v).toFixed(1)}`).join(' ')} L${x(now).toFixed(1)},${y(spent).toFixed(1)}`
  const area = `${line} L${x(now)},${y(0)} Z`
  const waves = withUsage.flatMap(({ r, ws }) => ws.waves.flatMap(w => {
    const t = Date.parse(w.startedAt ?? '')
    return t >= start && t <= now ? [{ key: `${r.name}\0${ws.name}\0${w.n}`, t, label: `Wave ${w.n} started · ${ws.name} · ${hm(t)}` }] : []
  }))
  const top = withUsage
    .map(({ ws }) => ({ ws, p: todayPace(ws.series, null, now) }))
    .filter(({ p }) => p.spent > 0)
    .sort((a, b) => b.p.spent - a.p.spent)
    .slice(0, 4)
  return (
    <div className="pace">
      <div className="chart-wrap">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Cumulative spend today: ${usd(spent)} now, ${usd(projected)} projected`}>
          <defs>
            <linearGradient id="pace-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="var(--accent)" stopOpacity=".32" /><stop offset="1" stopColor="var(--accent)" stopOpacity="0" /></linearGradient>
          </defs>
          {cross != null && <rect className="over" x={x(cross)} y={T} width={x(end) - x(cross)} height={H - T - B} />}
          {[0.25, 0.5, 0.75, 1].map(f => <line key={f} x1={L} x2={W - R} y1={y(max * f / 1.08)} y2={y(max * f / 1.08)} stroke="var(--line)" />)}
          {[0.5, 1].map(f => <text key={f} x={L - 6} y={y(max * f / 1.08) + 4} textAnchor="end">{usd(max * f / 1.08)}</text>)}
          <path d={area} fill="url(#pace-fill)" />
          <path d={line} className="cum" />
          <line className="proj" x1={x(now)} x2={x(end)} y1={y(spent)} y2={y(projected)} />
          {budget != null && <line className="budget" x1={L} x2={W - R} y1={y(budget)} y2={y(budget)} />}
          <line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke="currentColor" />
          {hourTicks(start, end, 5).map(d => <text key={+d} x={x(+d)} y={H - 6} textAnchor="middle">{hm(+d)}</text>)}
          {waves.map(w => <g key={w.key} className="wtick"><title>{w.label}</title><rect x={x(w.t) - 5} y={H - B - 8} width={10} height={14} fill="transparent" /><line x1={x(w.t)} x2={x(w.t)} y1={H - B - 5} y2={H - B + 3} /></g>)}
        </svg>
      </div>
      <p className="pace-foot mono">{usd(spent)} now → {usd(projected)} projected{budget != null && <> · budget {usd(budget)}</>}</p>
      {top.length > 0 && (
        <ol className="ws-rank">
          {top.map(({ ws, p }) => (
            <li key={ws.path + ws.name}>
              <span className="nm">{ws.name}</span><span className="mono">{usd(p.spent)}</span>
              <span className="split" aria-hidden>{p.models.slice(0, 4).map((m, i) => <i key={m.model} title={`${m.model} ${usd(m.cost)}`} style={{ width: `${(100 * m.cost) / p.spent}%`, background: SPLIT[i] }} />)}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
