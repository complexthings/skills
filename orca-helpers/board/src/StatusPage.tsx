// The Status Page (Board design pick 3): every repo's Needs you list, usage, spend, then the
// active Workstreams' lanes and every PR under review.
import { Link, Tabs } from '@radix-ui/themes'
import { useState } from 'react'
import { post, SlidingTabs } from './common'
import { ReviewsTab } from './ReviewsTab'
import { SpendPanel } from './SpendPanel'
import { Swimlane } from './Swimlane'
import { laneKey, repoKey, type Attention, type Board, type Repo } from './types'
import { UsageChart } from './UsageChart'

export type Need = {
  key: string
  action: 'Approve' | 'Open' | 'Jump'
  label: string
  tone: 'fail' | 'warn' | 'info'
  id: string
  title: string
  where: string
  repo: Repo | undefined
  jump: { repoPath: string; workstream: string } | null
  url: string | null
}

const LABEL = { question: 'Question', gate: 'Decision Gate', review_draft: 'Review Draft', failed: 'Failed' } as const
const VERDICT = { APPROVE: 'Approve', REQUEST_CHANGES: 'Request changes', COMMENT: 'Comment' } as const

/** The repo a name names: its Repo Name, or its `owner/repo` in any case. */
export const findRepo = (board: Board, name: string) => board.repos.find(r => r.name === name || r.slug?.toLowerCase() === name.toLowerCase())

const fromAttention = (board: Board, a: Attention): Need => ({
  action: a.kind === 'gate' ? 'Approve' : a.kind === 'review_draft' ? 'Open' : 'Jump',
  key: `${a.kind}\0${a.repoPath}\0${a.workstream}\0${a.item?.id ?? ''}`,
  label: LABEL[a.kind],
  tone: a.kind === 'failed' ? 'fail' : a.kind === 'review_draft' ? 'info' : 'warn',
  id: a.item?.id ?? a.workstream,
  title: (a.item ? a.item.title : a.question) ?? '',
  where: [a.kind === 'review_draft' ? a.repo : `${a.repo} / ${a.workstream}`, a.verdict && VERDICT[a.verdict], a.reason ?? (a.options.length ? `Options: ${a.options.join(', ')}` : null)].filter(Boolean).join(' · '),
  repo: findRepo(board, a.repo),
  jump: a.canJump ? { repoPath: a.repoPath, workstream: a.workstream } : null,
  url: a.url,
})

/** What waits on the user: questions and gates, Review Drafts, PRs awaiting changes, NO-SHIP reviews, then failed Work Items. */
export function needsAttention(board: Board): Need[] {
  const asked = board.attention.filter(a => a.kind !== 'failed').map(a => fromAttention(board, a))
  const changes: Need[] = board.reviews.repos.flatMap(r =>
    r.prs.filter(p => p.column === 'changes_requested' && p.status !== 'MERGED' && p.status !== 'CLOSED').map(p => ({
      action: 'Open' as const, key: `changes\0${r.name}\0${p.number}`, label: 'Changes requested', tone: 'warn' as const, id: `#${p.number}`, title: p.title ?? '',
      where: `${r.name}${p.round ? ` · Round ${p.round}` : ''}`, repo: findRepo(board, r.name), jump: null, url: p.url,
    })),
  )
  const noShip: Need[] = board.repos.flatMap(r =>
    r.workstreams.flatMap(ws =>
      ws.waves.flatMap(w =>
        w.items.filter(i => i.review?.verdict === 'NO-SHIP' && i.column !== 'failed' && i.column !== 'complete').map(i => ({
          action: 'Jump' as const, key: `noship\0${laneKey(r, ws)}\0${i.id}`, label: 'NO-SHIP', tone: 'fail' as const, id: i.id, title: i.title,
          where: `${r.name} / ${ws.name} · Round ${i.review!.round}`, repo: r, jump: ws.active ? { repoPath: ws.path, workstream: ws.name } : null, url: null,
        })),
      ),
    ),
  )
  const failed = board.attention.filter(a => a.kind === 'failed').map(a => fromAttention(board, a))
  return [...asked, ...changes, ...noShip, ...failed]
}

// Jump runs `orca terminal switch` to the Owning Session; without one, it opens the PR, else the repo's page.
function NeedRow({ need, onOpen }: { need: Need; onOpen: (repo: string) => void }) {
  const [error, setError] = useState<string | null>(null)
  const jump = () =>
    need.jump
      ? post('/api/jump', need.jump).then(r => setError(r.ok ? null : r.error), () => setError('The Board server is not answering. Run /orca-board to start it again.'))
      : need.url
        ? window.open(need.url, '_blank', 'noreferrer')
        : need.repo && onOpen(repoKey(need.repo))
  return (
    // The whole row clicks; its own links and button keep their own click.
    <li className="need" onClick={e => (e.target as HTMLElement).closest('a,button') || jump()}>
      <span className={`pill ${need.tone}`}>{need.label}</span>
      <span className="mono id">{need.url ? <Link href={need.url} target="_blank" rel="noreferrer">{need.id}</Link> : need.id}</span>
      <b className="title">{need.title}</b>
      <span className="where">{need.where}</span>
      <button type="button" className="chip" onClick={jump} aria-label={`${need.action} ${need.id}`}>{need.action}</button>
      {error && <span role="alert" className="err">{error}</span>}
    </li>
  )
}

export function NeedsAttention({ needs, onOpen }: { needs: Need[]; onOpen: (repo: string) => void }) {
  if (needs.length === 0) return null
  return (
    <section className="panel" id="needs-you" aria-label="Needs you">
      <h2>Needs you <span className="badge">{needs.length}</span></h2>
      <ul className="needs">{needs.map(n => <NeedRow key={n.key} need={n} onOpen={onOpen} />)}</ul>
    </section>
  )
}

export function StatusPage({ board, onOpen, onBudget }: { board: Board; onOpen: (repo: string) => void; onBudget: (r: Repo) => void }) {
  const [tab, setTab] = useState('waves')
  const needs = needsAttention(board)
  const lanes = board.repos.flatMap(r => r.workstreams.filter(ws => ws.active).map(ws => ({ r, ws })))
  const prs = board.reviews.repos.reduce((n, r) => n + r.prs.length, 0)
  const loops = board.repos.filter(r => r.prReviewActive).length
  const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? '' : 's'}`
  return (
    <div className="sec">
      <div className="page-h">
        <h1>All repos</h1>
        <span className="muted">{plural(board.repos.length, 'repo')} · {plural(lanes.length, 'active run')} · {plural(loops, 'PR review loop')}</span>
      </div>
      <NeedsAttention needs={needs} onOpen={onOpen} />
      <div className="grid2">
        <section className="panel" aria-label="Usage"><h2>Today&apos;s pace</h2><UsageChart repos={board.repos} /></section>
        <div className="stack"><SpendPanel repos={board.repos} waiting={needs.length} /></div>
      </div>
      <div className="panel">
        <Tabs.Root value={tab} onValueChange={setTab}>
          <SlidingTabs tabs={[{ id: 'waves', label: 'Waves', n: lanes.length }, { id: 'reviews', label: 'Reviews', n: prs }]} value={tab} onChange={setTab} />
          <Tabs.Content value="waves">
            <div className="lanes">
              {lanes.length === 0 && <p className="hint">No active runs. Run /orca-execute in a repo to start one.</p>}
              {lanes.map(({ r, ws }) => (
                <Swimlane key={laneKey(r, ws)} repo={r} ws={ws} showRepo locked
                  action={<button type="button" className="chip" onClick={() => onOpen(repoKey(r))}>Open {r.name}</button>} />
              ))}
            </div>
          </Tabs.Content>
          <Tabs.Content value="reviews"><div style={{ paddingTop: 12 }}><ReviewsTab reviews={board.reviews} /></div></Tabs.Content>
        </Tabs.Root>
      </div>
    </div>
  )
}
