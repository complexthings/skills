// The Reviews tab (Board design pick 9): every orca-pr-review PR as a row under fixed column headers,
// rejected PRs first, then state and an age bar. Merged and closed PRs stay a while, greyed. A held Review Draft opens the draft modal.
import { Dialog, Link } from '@radix-ui/themes'
import { useState, type CSSProperties } from 'react'
import { elapsed, post } from './common'
import type { Review, ReviewColumn, Reviews } from './types'

const COLUMNS: Record<ReviewColumn, { heading: string; color: string; order: number }> = {
  changes_requested: { heading: 'Changes requested', color: 'var(--fail)', order: 0 },
  draft_ready: { heading: 'Draft ready', color: 'var(--run)', order: 1 },
  reviewing: { heading: 'Reviewing', color: 'var(--review)', order: 2 },
  new: { heading: 'New', color: 'var(--todo)', order: 3 },
  approved: { heading: 'Approved', color: 'var(--done)', order: 4 },
}
const EVENT: Record<string, string> = { APPROVE: 'Approve', REQUEST_CHANGES: 'Request changes', COMMENT: 'Comment' }
// The age bar fills over 4 hours.
const FULL_MS = 4 * 3600_000

type Row = Review & { repo: string }

const ageMs = (since: string | null) => Date.now() - Date.parse(since ?? '')

function ReviewRow({ pr, onDraft }: { pr: Row; onDraft: () => void }) {
  const finished = pr.status === 'MERGED' || pr.status === 'CLOSED'
  const c = finished ? { heading: pr.status === 'MERGED' ? 'Merged' : 'Closed', color: 'var(--fg3)' } : COLUMNS[pr.column]
  const since = finished ? pr.finishedAt : pr.claimedAt
  const ms = ageMs(since)
  // The underline grows with age and fills at 4 hours; amber only for open PRs that old.
  const width = Number.isFinite(ms) ? Math.max(6, Math.min(100, (ms / FULL_MS) * 100)) : 0
  const stale = !finished && ms >= FULL_MS
  return (
    <article className={`rrow${pr.column === 'draft_ready' && !finished ? ' ready' : ''}${finished ? ' merged' : ''}`} style={{ '--c': c.color } as CSSProperties} aria-label={`${pr.repo}#${pr.number}`}>
      <div className="rmain">
        <div className="ttl">{pr.title ?? 'Untitled'}</div>
        <div className="sub mono">{pr.url ? <Link href={pr.url} target="_blank" rel="noreferrer">#{pr.number}</Link> : `#${pr.number}`} · {pr.repo}</div>
      </div>
      <span className="rstate">
        <span className="pill">{c.heading}</span>
        {pr.mine && <span className="you" title="You reviewed this PR by hand">You</span>}
        {pr.held && <button type="button" className="chip" onClick={onDraft}>Review draft</button>}
      </span>
      <span className="age">
        <span className="mono">{elapsed(since) ?? '—'}</span>
        <span className={`abar${stale ? ' wait' : ''}`}><i style={{ width: `${width}%` }} /></span>
      </span>
    </article>
  )
}

type Result = { ok: true; message: string } | { ok: false; fail: string[] }

/** The held Review Draft, with Publish Review and Adjust Review. Radix Dialog traps focus and closes on Escape. */
export function DraftModal({ pr, onClose }: { pr: Row; onClose: () => void }) {
  const id = `${pr.repo}#${pr.number}`
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<Result | null>(null)
  const send = (url: string, body: object, message: string) => {
    setBusy(true)
    setResult(null)
    post(url, body)
      .then(r => setResult(r?.ok ? { ok: true, message } : { ok: false, fail: Array.isArray(r?.fail) ? r.fail : ['FAIL: the Board server sent no reason.'] }))
      .catch(() => setResult({ ok: false, fail: ['FAIL: the Board server did not answer.'] }))
      .finally(() => setBusy(false))
  }
  const done = result?.ok === true
  return (
    <Dialog.Root open onOpenChange={o => !o && onClose()}>
      <Dialog.Content className="modal" maxWidth="640px">
        <Dialog.Title>Review draft · {id}</Dialog.Title>
        <Dialog.Description size="2" color="gray">
          {pr.title ?? 'Untitled'} · {pr.draft ? EVENT[pr.draft.event] ?? pr.draft.event : 'no event'} · Round {pr.round ?? 0}
        </Dialog.Description>
        <pre className="draft">{pr.draft?.body || 'The draft has no body.'}</pre>
        <label className="fb">
          <span>Review Feedback for the review worker</span>
          <textarea rows={3} value={text} maxLength={20000} disabled={busy || done} onChange={e => setText(e.target.value)} placeholder="What should the review change?" />
        </label>
        {result && (
          <div className={`result ${result.ok ? 'ok' : 'bad'}`} role="status">
            {result.ok ? result.message : result.fail.map((f, i) => <div key={i}>{f}</div>)}
          </div>
        )}
        <div className="modal-foot">
          <Dialog.Close><button type="button" className="chip">{done ? 'Close' : 'Cancel'}</button></Dialog.Close>
          <button type="button" className="chip" disabled={busy || done || !text.trim()}
            onClick={() => send('/api/review/feedback', { pr: id, text: text.trim() }, 'Feedback sent. The review worker rewrites the draft and holds it again.')}>Adjust Review</button>
          <button type="button" className="chip primary" disabled={busy || done}
            onClick={() => send('/api/review/approve', { pr: id }, 'Review published to GitHub.')}>Publish Review</button>
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

/** `reviews` holds the repos to show: every one on the Status Page, one on a Repo Status Page. */
export function ReviewsTab({ reviews }: { reviews: Reviews }) {
  const [filter, setFilter] = useState<ReviewColumn | 'all'>('all')
  // A snapshot, so the modal keeps its draft after a poll drops the row's `held`.
  const [open, setOpen] = useState<Row | null>(null)
  const rows: Row[] = reviews.repos.flatMap(r => r.prs.map(p => ({ ...p, repo: r.name })))
  const shown = rows
    .filter(r => filter === 'all' || r.column === filter)
    .sort((a, b) => COLUMNS[a.column].order - COLUMNS[b.column].order || (ageMs(b.claimedAt) || 0) - (ageMs(a.claimedAt) || 0))
  if (rows.length === 0) return <div className="sec"><p className="hint">No PRs under review. Run /orca-pr-review start to begin the loop.</p></div>
  return (
    <div className="sec">
      <div className="chips" role="group" aria-label="Filter reviews">
        {(['all', ...Object.keys(COLUMNS)] as const).map(v => (
          <button key={v} type="button" className="chip" aria-pressed={filter === v} onClick={() => setFilter(v as ReviewColumn | 'all')}>
            {v === 'all' ? 'All' : COLUMNS[v as ReviewColumn].heading} <span className="mono muted">{v === 'all' ? rows.length : rows.filter(r => r.column === v).length}</span>
          </button>
        ))}
      </div>
      <div className="rlist">
        <div className="rrow hd" aria-hidden="true"><span>Pull request</span><span>State</span><span>Age</span></div>
        {shown.map(p => <ReviewRow key={`${p.repo}#${p.number}`} pr={p} onDraft={() => setOpen(p)} />)}
        {shown.length === 0 && <p className="hint">No reviews match this filter.</p>}
      </div>
      {open && <DraftModal pr={open} onClose={() => setOpen(null)} />}
    </div>
  )
}
