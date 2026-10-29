// The /api/board payload, as board.py's docstring describes it.
import type { Series } from './usage'

export type Pr = { number: number; url: string | null; state: string | null }
export type Column = 'todo' | 'in_progress' | 'reviewing' | 'complete' | 'failed'
export type Usage = { cost: number; input: number; output: number; cacheRead: number; cacheWrite: number }
export type Totals = Usage & { missing: number }
export type Item = {
  id: string
  title: string
  column: Column
  harness: string | null
  mood: string | null
  model: string | null
  effort: string | null
  pr: Pr | null
  enteredAt: string | null
  reason: string | null
  progress: { done: number; total: number; note: string } | null
  review: { round: number; verdict: 'SHIP' | 'NO-SHIP' | null; reviewer: string } | null
  usage: Usage | null
}
export type Wave = { n: number; title: string; state: string; startedAt: string | null; totals: Totals | null; items: Item[] }
export type Workstream = {
  name: string
  path: string
  state: 'active' | 'finished' | 'stopped'
  mainOrchestrator: { harness: string | null; model: string | null; effort: string | null }
  taskTime: string
  started: boolean
  active: boolean
  lastChange: string | null
  totals: Totals | null
  budgetUsd: number | null
  maxConcurrency: number | null
  running: number
  /** The `_config.json` keys a Workstream may override, as stored. */
  config: Partial<Settings>
  series: Series | null
  waves: Wave[]
}
export type Repo = {
  name: string
  path: string | null
  slug: string | null
  executeActive: boolean
  prReviewActive: boolean
  totals: Totals | null
  /** Prompt Settings as `write_settings.py --read` prints them; null with no checkout or no valid file. */
  settings: Settings | null
  workstreams: Workstream[]
}
export type Slot = string | { model: string; effort: string | null } | null
export type SlotName = 'mainOrchestrator' | 'orchestrationWorker' | 'subagent' | 'subagentSimple'
export type Harness = { name: string; cli: string | null; tier: 'light' | 'standard'; models: Record<SlotName, Slot> }
export type Settings = {
  harnesses: Harness[]
  mainOrchestratorHarness: string | null
  targetBranch: string
  maxConcurrency: number | null
  priorityFile?: string
  review?: boolean
  planGate?: boolean
  evidenceCommand?: string | null
  budgetUsd?: number | null
  taskTime?: string
}
export type Attention = {
  kind: 'question' | 'gate' | 'review_draft' | 'failed'
  repo: string
  repoPath: string
  workstream: string
  question: string | null
  options: string[]
  askedAt: string | null
  item: { id: string; title: string } | null
  reason: string | null
  canJump: boolean
  verdict: 'APPROVE' | 'REQUEST_CHANGES' | 'COMMENT' | null
  url: string | null
}
export type ReviewColumn = 'new' | 'reviewing' | 'draft_ready' | 'changes_requested' | 'approved'
export type Review = {
  number: number
  url: string | null
  title: string | null
  author: string | null
  assignees: string[] | null
  head: string | null
  base: string | null
  checks: { passed: number; total: number } | null
  status: string | null
  round: number | null
  harness: string | null
  column: ReviewColumn
  claimedAt: string | null
  held: boolean
  draft: { event: string; body: string } | null
  mine: boolean
  finishedAt: string | null
}
export type Reviews = { repos: { name: string; prs: Review[] }[] }
export type Board = { generatedAt: string; attention: Attention[]; repos: Repo[]; reviews: Reviews }

/** A repo's identity: its main checkout, or its `owner/repo` for a Watched Repo with no checkout. */
export const repoKey = (r: Repo) => r.path ?? r.slug ?? r.name
/** A Workstream view's identity: the repo plus the name, so two repos' Workstreams of one name never share state. */
export const laneKey = (r: Repo, ws: Workstream) => `${repoKey(r)}\0${ws.name}`
/** The Wave in flight, else the last one. */
export const currentWave = (ws: Workstream) => ws.waves.find(w => w.state === 'active') ?? ws.waves[ws.waves.length - 1]
/** The Wave filter a lane applies: the Status Page pins the active Wave, and a finished Workstream turns a stale Active Wave filter into All Waves. */
export const waveFilter = (filter: string, ws: Workstream, locked?: boolean) => (locked ? 'active' : filter === 'active' && !ws.active ? 'all' : filter)

// Spend against the repo's Workstream budgets: only budgeted Workstreams count, so both sides cover the same set.
// With no budget at all, spent is the whole repo's spend.
export function repoSpend(repo: Repo) {
  const budgeted = repo.workstreams.filter(ws => ws.budgetUsd != null)
  const sum = (list: Workstream[], f: (ws: Workstream) => number) => list.reduce((n, ws) => n + f(ws), 0)
  const spent = sum(budgeted.length ? budgeted : repo.workstreams, ws => ws.totals?.cost ?? 0)
  return { spent, budget: budgeted.length ? sum(budgeted, ws => ws.budgetUsd ?? 0) : null }
}
