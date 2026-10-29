// The Spend card (one big number, the page's strongest lift) and the Running agents card: the running
// count, an amber waiting-on-you count that links to Needs you, and one slot cell per maxConcurrency slot.
import type { Repo } from './types'

const usd = (n: number) => `$${n.toFixed(2)}`

/** Spend and running agents for `repos`. `waiting` is the Needs you count. */
export function SpendPanel({ repos, waiting }: { repos: Repo[]; waiting: number }) {
  const every = repos.flatMap(r => r.workstreams)
  const spend = every.reduce((n, ws) => n + (ws.totals?.cost ?? 0), 0)
  const running = every.reduce((n, ws) => n + ws.running, 0)
  const active = every.filter(ws => ws.active && ws.maxConcurrency != null)
  const c = active.length ? active.reduce((n, ws) => n + ws.maxConcurrency!, 0) : null
  return (
    <>
      <section className="panel spend lift" aria-label="Spend">
        <div className="eyebrow">Spend</div>
        <div className="big mono">{usd(spend)}</div>
      </section>
      <section className="panel agents" aria-label="Running agents">
        <div className="eyebrow">Running agents</div>
        <div className="agents-n">
          <b className="mono">{running}</b>
          {waiting > 0 && <a className="waiting" href="#needs-you">{waiting} waiting on you</a>}
        </div>
        {c != null && (
          <div className="slots" role="img" aria-label={`${running} of ${c} slots busy`}>
            {Array.from({ length: c }, (_, i) => <i key={i} className={i < running ? 'busy' : ''} />)}
          </div>
        )}
      </section>
    </>
  )
}
