// The Repo Status Page (Board design pick 4): one repo's usage, spend and its Waves, Reviews and Config tabs.
// Active lanes come first, then Finished and Planned dividers; a repo with PR review off offers "Turn on".
import { Tabs } from '@radix-ui/themes'
import { useState } from 'react'
import { ConfigTab, overridden } from './ConfigTab'
import { SlidingTabs } from './common'
import { ReviewsTab } from './ReviewsTab'
import { SpendPanel } from './SpendPanel'
import { NeedsAttention, needsAttention } from './StatusPage'
import { Swimlane } from './Swimlane'
import { laneKey, repoKey, type Board, type Repo, type Workstream } from './types'
import { UsageChart } from './UsageChart'

export type RepoTab = 'waves' | 'reviews' | 'config'

/** Focus the Config tab's budget field, `#budgetUsd`, once the tab has rendered. */
export const focusBudget = () => requestAnimationFrame(() => requestAnimationFrame(() => document.getElementById('budgetUsd')?.focus()))

function Copy({ text }: { text: string }) {
  const [done, setDone] = useState(false)
  const copy = () => navigator.clipboard.writeText(text).then(() => (setDone(true), setTimeout(() => setDone(false), 1500)), () => {})
  return (
    <div className="cmd">
      <code>{text}</code>
      <button type="button" className="chip" onClick={copy} aria-label={`Copy ${text}`}>{done ? 'Copied' : 'Copy'}</button>
    </div>
  )
}

/** The two commands that start orca-pr-review on this repo. */
export const TurnOn = ({ repo }: { repo: Repo }) => (
  <div className="turn-on">
    <p className="hint">Run these in a Claude Code session to review this repo's PRs:</p>
    <Copy text={`/orca-pr-review watch ${repo.slug ?? '<owner/repo>'}`} />
    <Copy text="/orca-pr-review start" />
  </div>
)

export function RepoStatusPage({ board, repo, tab, onTab }: { board: Board; repo: Repo; tab: RepoTab; onTab: (t: RepoTab) => void }) {
  const [turnOn, setTurnOn] = useState(false)
  const [unsaved, setUnsaved] = useState(0)
  const reviews = { repos: board.reviews.repos.filter(r => r.name.toLowerCase() === repo.slug?.toLowerCase()) }
  const prs = reviews.repos.reduce((n, r) => n + r.prs.length, 0)
  const active = repo.workstreams.filter(ws => ws.active)
  const finished = repo.workstreams.filter(ws => !ws.active && ws.started)
  const planned = repo.workstreams.filter(ws => !ws.started)
  const needs = needsAttention(board).filter(n => n.repo && repoKey(n.repo) === repoKey(repo))
  const overrides = repo.workstreams.filter(ws => overridden(repo, ws).length > 0).length
  const dot = [unsaved && `${unsaved} unsaved change${unsaved === 1 ? '' : 's'}`, overrides && `${overrides} Workstream${overrides === 1 ? '' : 's'} with overrides`].filter(Boolean).join(', ')
  const lane = (ws: Workstream) => (
    <Swimlane key={laneKey(repo, ws)} repo={repo} ws={ws} />
  )
  const group = (title: string, list: Workstream[]) =>
    list.length > 0 && (
      <>
        <div className="divider eyebrow">{title} ({list.length})</div>
        {list.map(lane)}
      </>
    )
  return (
    <div className="sec">
      <div className="page-h">
        <h1>{repo.name}</h1>
        <span className="mono muted path">{repo.path ?? repo.slug}</span>
        <span className="muted">
          · {active.length} active run{active.length === 1 ? '' : 's'} · PR review {repo.prReviewActive ? 'on' : 'off'}
          {!repo.prReviewActive && <> · <button type="button" className="linkish" aria-expanded={turnOn} onClick={() => setTurnOn(!turnOn)}>Turn on</button></>}
        </span>
      </div>
      {turnOn && !repo.prReviewActive && <div className="panel"><TurnOn repo={repo} /></div>}
      <NeedsAttention needs={needs} onOpen={() => onTab('waves')} />
      <div className="grid2">
        <section className="panel" aria-label="Usage"><h2>Today&apos;s pace</h2><UsageChart repos={[repo]} /></section>
        <div className="stack"><SpendPanel repos={[repo]} waiting={needs.length} /></div>
      </div>
      <div className="panel">
        <Tabs.Root value={tab} onValueChange={v => onTab(v as RepoTab)}>
          <SlidingTabs
            tabs={[
              { id: 'waves', label: 'Waves', n: repo.workstreams.length },
              { id: 'reviews', label: 'Reviews', n: prs },
              { id: 'config', label: 'Config', dot: dot || undefined },
            ]}
            value={tab}
            onChange={v => onTab(v as RepoTab)}
          />
          <Tabs.Content value="waves">
            <div className="lanes">
              {repo.workstreams.length === 0 && <p className="hint">No Workstreams yet. Run /orca-execute in this repo to start one.</p>}
              {active.map(lane)}
              {group('Finished', finished)}
              {group('Planned', planned)}
            </div>
          </Tabs.Content>
          <Tabs.Content value="reviews">
            <div style={{ paddingTop: 12 }}>
              {prs === 0 && !repo.prReviewActive ? <TurnOn repo={repo} /> : <ReviewsTab reviews={reviews} />}
            </div>
          </Tabs.Content>
          {/* Kept mounted, so unsaved changes survive a visit to another tab. */}
          <Tabs.Content value="config" forceMount className="keep"><div style={{ paddingTop: 12 }}><ConfigTab repo={repo} onUnsaved={setUnsaved} /></div></Tabs.Content>
        </Tabs.Root>
      </div>
    </div>
  )
}
