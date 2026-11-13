// The sidebar (Board design pick 1): logo, All, one row per repo with its Wave progress and spend, labelled run
// and PR-loop dots and an attention count, then the Needs you list and the dot legend. Phones get a
// repo dropdown and a strip of active Workstreams that scrolls on its own. Every row truncates, so the
// sidebar never scrolls sideways.
import { Select } from '@radix-ui/themes'
import logo from '../../hooks/assets/orca_0.png'
import type { Need } from './StatusPage'
import { currentWave, repoKey, repoSpend, type Board, type Repo } from './types'

const ALL = '\0all'

function WaveBar({ repo }: { repo: Repo }) {
  const ws = repo.workstreams.find(w => w.active)
  const wave = ws && currentWave(ws)
  if (!ws || !wave) return <span className="sub">no active run</span>
  return (
    <span className="sub" title={`${ws.name}: Wave ${wave.n} of ${ws.waves.length}`}>
      W{wave.n}/{ws.waves.length}
      <span className="wbar" aria-hidden>{ws.waves.map(w => <i key={w.n} className={w.state} />)}</span>
    </span>
  )
}

// Spent against the repo's Workstream budgets, with a thin meter under it.
function Spend({ repo }: { repo: Repo }) {
  const { spent, budget } = repoSpend(repo)
  return (
    <>
      <span className="sub">${spent.toFixed(2)} / {budget == null ? 'no budget' : `$${budget.toFixed(2)}`}</span>
      <span className="bar-meter thin side-meter" aria-hidden><i style={{ width: `${budget ? Math.min(100, (100 * spent) / budget) : 0}%` }} /></span>
    </>
  )
}

export function Sidebar({ board, current, needs, onOpen }: { board: Board | null; current: string | null; needs: Need[]; onOpen: (repo: string | null) => void }) {
  const repos = board?.repos ?? []
  const count = (r: Repo) => needs.filter(n => n.repo && repoKey(n.repo) === repoKey(r)).length
  return (
    <aside className="side" aria-label="Repositories">
      <button type="button" className="logo" onClick={() => onOpen(null)}>
        <img src={logo} alt="" width={24} height={24} />Orca Helpers
      </button>
      <div className="side-pick">
        <Select.Root value={current ?? ALL} onValueChange={v => onOpen(v === ALL ? null : v)}>
          <Select.Trigger aria-label="Repo" />
          <Select.Content>
            <Select.Item value={ALL}>All repos</Select.Item>
            {repos.map(r => <Select.Item key={repoKey(r)} value={repoKey(r)}>{r.name}</Select.Item>)}
          </Select.Content>
        </Select.Root>
      </div>
      <nav className="side-ws" aria-label="Active Workstreams">
        {repos.flatMap(r => r.workstreams.filter(ws => ws.active).map(ws => (
          <button key={repoKey(r) + ws.name} type="button" className="row" onClick={() => onOpen(repoKey(r))}>
            <span className="nm"><span className="t">{ws.name}</span><span className="sub">{r.name}</span></span>
          </button>
        )))}
      </nav>
      <nav className="side-list">
        <button type="button" className="row all" aria-current={current == null ? 'page' : undefined} onClick={() => onOpen(null)}>
          <span className="ico" aria-hidden>▦</span><span className="nm">All</span>
        </button>
        <div className="eyebrow">Repos</div>
        {repos.length === 0 && <p className="hint">No repos yet. Run /orca-execute or /orca-pr-review watch.</p>}
        {repos.map(r => {
          const n = count(r)
          return (
            <button key={repoKey(r)} type="button" className="row" aria-current={current === repoKey(r) ? 'page' : undefined} onClick={() => onOpen(repoKey(r))} title={r.path ?? r.slug ?? r.name}>
              <span className="ico" aria-hidden>▤</span>
              <span className="nm">
                <span className="t">{r.name}</span>
                <WaveBar repo={r} />
                <Spend repo={r} />
              </span>
              <span className="dots">
                {r.executeActive && <span className="dot run">run</span>}
                {r.prReviewActive && <span className="dot pr">PR</span>}
              </span>
              {n > 0 && <span className={`badge${needs.some(x => x.tone === 'fail' && x.repo === r) ? ' fail' : ''}`} aria-label={`${n} need attention`}>{n}</span>}
            </button>
          )
        })}
      </nav>
      {needs.length > 0 && (
        <section className="side-needs" aria-label="Needs you">
          <div className="eyebrow">Needs you · {needs.length}</div>
          {needs.map(n => (
            <button key={n.key} type="button" className="need-row" onClick={() => n.repo && onOpen(repoKey(n.repo))} title={`${n.id} ${n.title}`}>
              <span className={`pill ${n.tone}`}>{n.label}</span>
              <span className="mono t">{n.id}</span>
              <span className="muted t">{n.repo?.name}</span>
            </button>
          ))}
        </section>
      )}
      <div className="legend-side">
        <span><span className="dot run" />orca-execute run</span>
        <span><span className="dot pr" />orca-pr-review loop</span>
        <span className="mono muted">{location.host}</span>
      </div>
    </aside>
  )
}
