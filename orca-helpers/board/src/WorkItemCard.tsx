// One Work Item on a Kanban column (Board design pick 8): state word, id and title on top, an amber
// Reviewing card with a gold border beam, the progress note as a quiet second line, and the time
// in the Work Item against its Task Time.
import { Link } from '@radix-ui/themes'
import { Avatar, Card, HARNESSES, elapsed, money, usageTitle } from './common'
import type { Column, Item } from './types'

// The Avatar State per column, as avatarState in hooks/waves.ts: failed and reviewing keep the progress art.
const AVATAR_STATE = { todo: 'todo', in_progress: 'progress', reviewing: 'progress', complete: 'complete', failed: 'progress' } as const
export const COLUMNS: { id: Column; heading: string; status: string; color: string }[] = [
  { id: 'todo', heading: 'Todo', status: 'Queued', color: 'var(--todo)' },
  { id: 'in_progress', heading: 'Running', status: 'Running', color: 'var(--run)' },
  { id: 'reviewing', heading: 'In review', status: 'In review', color: 'var(--review)' },
  { id: 'complete', heading: 'Done', status: 'Done', color: 'var(--done)' },
  { id: 'failed', heading: 'Failed', status: 'Failed', color: 'var(--fail)' },
]

// Task Time in minutes; ultra has no limit, so its cards show elapsed time only.
const TASK_MINUTES: Record<string, number> = { low: 5, medium: 10, high: 15, xhigh: 30 }

export function WorkItemCard({ item, wave, showWave, taskTime }: { item: Item; wave: number; showWave: boolean; taskTime?: string }) {
  const col = COLUMNS.find(c => c.id === item.column)!
  const time = elapsed(item.enteredAt)
  const limit = item.column === 'complete' ? undefined : TASK_MINUTES[taskTime ?? '']
  const over = limit != null && time != null && (Date.now() - Date.parse(item.enteredAt!)) / 60000 > limit
  const p = item.column === 'in_progress' ? item.progress : null
  const reviewer = item.column === 'reviewing' ? item.review : null
  return (
    <Card className={item.column}>
      <div className="card-top">
        <div className="avs">
          <Avatar harness={item.harness} state={AVATAR_STATE[item.column]} mood={item.mood} status={col.status.toLowerCase()} />
        </div>
        <div className="t">
          <div className="card-st"><i />{item.column === 'in_progress' ? <span className="shiny">{col.status}</span> : col.status}</div>
          <div className="card-id">{item.id}</div>
          <div className="card-title">{item.title}</div>
          {p?.note && <div className="card-note">{p.note}</div>}
        </div>
      </div>
      <div className="meta">
        {showWave && <span className="tag w">Wave {wave}</span>}
        {item.model ? <span className="tag">{item.model}{item.effort ? ` · ${item.effort}` : ''}</span> : item.harness && <span className="tag">{item.harness}</span>}
        {item.pr && (
          <span className="tag mono">
            {item.pr.url ? <Link href={item.pr.url} target="_blank" rel="noreferrer">#{item.pr.number}</Link> : `#${item.pr.number}`}
            {item.pr.state ? ` ${item.pr.state.toLowerCase()}` : ''}
          </span>
        )}
      </div>
      {reviewer && (
        <div className="rv">
          {reviewer.reviewer && <Avatar harness={reviewer.reviewer} state="progress" mood={null} status="reviewing" />}
          <span><b>{HARNESSES[reviewer.reviewer]?.title ?? reviewer.reviewer}</b> · Round {reviewer.round}</span>
          {reviewer.verdict && <span className={`tag ${reviewer.verdict === 'SHIP' ? 'ship' : 'noship'}`}>{reviewer.verdict}</span>}
        </div>
      )}
      {p && (
        <div className="prog">
          <div className="track" role="progressbar" aria-label={`${item.id} progress`} aria-valuemin={0} aria-valuemax={p.total} aria-valuenow={Math.min(p.done, p.total)}>
            <i style={{ width: `${(100 * Math.min(p.done, p.total)) / Math.max(1, p.total)}%` }} />
          </div>
          <div className="cap"><span className="mono">{p.done}/{p.total}</span></div>
        </div>
      )}
      {item.column === 'failed' && <div className="reason">{item.reason ?? 'No reason given'}</div>}
      <div className="foot">
        <span className="mono" title={usageTitle(item.usage)}>{money(item.usage)}</span>
        <span className={over ? 'over' : undefined}>{item.column === 'todo' ? 'queued' : time ? `${time}${limit != null ? ` / ${limit}m` : ''}` : ''}</span>
      </div>
    </Card>
  )
}
