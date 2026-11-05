// One Workstream's lane (Board design pick 7): a header that folds and keeps a summary when folded,
// a segmented Wave timeline, then Kanban columns where empty ones shrink to rails and Failed comes first.
// Mount it keyed by laneKey(), so its Wave filter belongs to one repo's Workstream.
import type { CSSProperties, ReactNode } from 'react'
import { useState } from 'react'
import { HARNESSES, money } from './common'
import { COLUMNS, WorkItemCard } from './WorkItemCard'
import { currentWave, waveFilter, type Repo, type Wave, type Workstream } from './types'
import { WorkstreamConfigModal } from './WorkstreamConfigModal'

const STATE = { active: 'Running', finished: 'Finished', stopped: 'Stopped' } as const

/** `locked` (the Status Page) pins the lane to its active Wave and hides the timeline and Config. */
export function Swimlane({ repo, ws, showRepo, locked, action }: { repo: Repo; ws: Workstream; showRepo?: boolean; locked?: boolean; action?: ReactNode }) {
  const [filter, setFilter] = useState(ws.active ? 'active' : 'all')
  const [open, setOpen] = useState(ws.active)
  const [config, setConfig] = useState(false)
  const wave = currentWave(ws)
  const f = waveFilter(filter, ws, locked)
  const shown = ws.waves.filter(w => f === 'all' || (f === 'active' ? w === wave : String(w.n) === f))
  const m = ws.mainOrchestrator
  const art = HARNESSES[m.harness ?? '']?.art ?? 'claude'
  const state = ws.started ? STATE[ws.state] : 'Not started'
  const done = (w: Wave) => w.items.filter(i => i.column === 'complete').length
  const dot = (w: Wave) => (!ws.started ? 'todo' : !ws.active || done(w) === w.items.length ? 'done' : w === wave ? 'cur' : 'todo')
  const all = ws.waves.flatMap(w => w.items)
  const cols = COLUMNS.map(c => ({ c, items: shown.flatMap(w => w.items.filter(i => i.column === c.id).map(i => <WorkItemCard key={i.id} item={i} wave={w.n} showWave={f === 'all'} taskTime={ws.taskTime} />)) }))
  if (cols[4]!.items.length) cols.unshift(cols.pop()!)
  const segs: [string, string, Wave?][] = [['all', 'All Waves'], ...(ws.active ? [['active', 'Active Wave'] as [string, string]] : []), ...ws.waves.map(w => [String(w.n), `Wave ${w.n}`, w] as [string, string, Wave])]
  return (
    <section className={`lane ${ws.active ? 'on' : 'off'}`} data-open={open} aria-label={`${repo.name} / ${ws.name}`}>
      <div className="lane-h">
        <button type="button" className="lane-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
          <span className="chev" aria-hidden="true">▸</span>
          <span className="lane-id">
            <img className="crown" src={`avatars/${art}_main_0.svg`} alt="" width={36} height={36} />
            <span className="t">
              <span className="name">
                {showRepo && <span className="muted">{repo.name} / </span>}<b>{ws.name}</b>
                <span className={`pill ${ws.active ? 'run' : ''}`}>{state}</span>
              </span>
              <span className="sub">
                <b>Main Orchestrator</b> · {[HARNESSES[m.harness ?? '']?.title ?? m.harness, m.model, m.effort].filter(Boolean).join(' · ') || 'unknown'}
              </span>
            </span>
          </span>
          <span className="wstat">
            <b>{ws.active ? `Wave ${wave?.n} of ${ws.waves.length}` : ws.started ? `All ${ws.waves.length} Waves done` : 'Not started'}</b>
            <span className="wdots">
              {ws.waves.map(w => <i key={w.n} className={dot(w)} title={`Wave ${w.n}: ${w.title}`}>{w.n}</i>)}
            </span>
            <span className="hint">{ws.active ? wave?.title : ws.started ? 'Finished' : `${ws.waves.length} Waves planned`}</span>
          </span>
          <span className="counts" aria-label="Work Items by state">
            {COLUMNS.map(c => {
              const n = all.filter(i => i.column === c.id).length
              return n > 0 && <span key={c.id} style={{ '--c': c.color } as CSSProperties}><i />{n} {c.heading.toLowerCase()}</span>
            })}
          </span>
          <span className="lmeta mono">{ws.started ? money(ws.totals) : '—'}{ws.budgetUsd != null && <span className="muted"> / ${ws.budgetUsd.toFixed(2)}</span>}</span>
        </button>
        {!locked && !ws.active && <button type="button" className="chip" onClick={() => setConfig(true)}>⚙ Config</button>}
        {action}
      </div>
      {open && (
        <div className="lane-body">
          {ws.waves.length === 0 ? (
            <p className="hint">No Waves yet. Work Items show here once orca-execute records them.</p>
          ) : (
            <>
              {locked ? (
                <p className="hint">Showing only the active Wave: <b>Wave {wave?.n} · {wave?.title}</b></p>
              ) : (
                <div className="wtl" role="radiogroup" aria-label={`Wave for ${ws.name}`}>
                  {segs.map(([v, label, w]) => (
                    <button key={v} type="button" role="radio" aria-checked={f === v} className={`wseg ${w ? dot(w) : ''}`}
                      style={w && { '--p': `${(100 * done(w)) / Math.max(1, w.items.length)}%` } as CSSProperties} onClick={() => setFilter(v)}>
                      <b>{label}</b>
                      {w && <span>{w.title}</span>}
                      {w && <em className="mono">{done(w)}/{w.items.length}</em>}
                    </button>
                  ))}
                </div>
              )}
              <div className="kb flexkb" tabIndex={0} aria-label={`Work Items for ${ws.name}`}>
                {cols.map(({ c, items }) =>
                  items.length ? (
                    <section key={c.id} className={`col${c.id === 'failed' ? ' hot' : ''}`} style={{ '--c': c.color } as CSSProperties} aria-label={c.heading}>
                      <h3 className="col-h"><span className="dot" />{c.heading}<span className="n">{items.length}</span></h3>
                      {items}
                    </section>
                  ) : (
                    <section key={c.id} className="col rail" style={{ '--c': c.color } as CSSProperties} aria-label={`${c.heading}, empty`}>
                      <span className="n mono">0</span><span className="v">{c.heading}</span>
                    </section>
                  ),
                )}
              </div>
            </>
          )}
        </div>
      )}
      {config && <WorkstreamConfigModal repo={repo} workstream={ws} onClose={() => setConfig(false)} />}
    </section>
  )
}
