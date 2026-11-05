// The Wave band's window and current-Wave logic, kept pure so it is tested
// without a drawing. Reads a _status.json as set_status.py writes it.

export type State = 'todo' | 'in_progress' | 'reviewing' | 'complete' | 'failed'
export type Progress = { done: number; total: number; note: string; at: string }
export type Review = { round: number; verdict: 'SHIP' | 'NO-SHIP' | null; reviewer: string }
export type Item = { id: string; title: string; wave: number; state: State; reason?: string | null; harness?: string | null; pr?: number | null; progress?: Progress | null; review?: Review }
export type Status = { workstream: string; active: boolean; startedAt?: string | null; finishedAt?: string | null; items: Item[] }

export type Wave = { wave: number; complete: number; total: number; kind: 'complete' | 'current' | 'upcoming' }
export type Slot = Wave | { more: number }
export type View = {
  workstream: string
  slots: Slot[]
  current: number
  // The Wave the columns draw: a pinned one, else the current one.
  shown: number
  failed: Item[]
  todo: Item[]
  inProgress: Item[]
  reviewing: Item[]
  complete: Item[]
}

const MAX_SLOTS = 4

// A Work Item's Harness Avatar: its column's Avatar State, a Mood, and the art
// to draw, as art/avatars/export.mjs names them `<art>_<state>_<mood>_<size>`.
export type AvatarState = 'todo' | 'progress' | 'complete'
export const MOODS = ['default', 'red', 'blue', 'green', 'yellow', 'purple', 'teal'] as const
export type Mood = (typeof MOODS)[number]

// A failed or reviewing item draws the progress state: neither is done yet.
export const avatarState = (state: State): AvatarState =>
  state === 'todo' ? 'todo' : state === 'complete' ? 'complete' : 'progress'

const fnv = (text: string) => {
  let hash = 0x811c9dc5
  for (const c of text) hash = Math.imul(hash ^ c.codePointAt(0)!, 0x01000193)
  return hash >>> 0
}

// The Wave's Moods in an order FNV-1a picks from workstream and Wave, dealt to its
// items in order, so every redraw picks the same Mood and no two of up to 7 items share one.
export const avatarMood = (workstream: string, wave: number, ids: string[], id: string): Mood => {
  const deck = [...MOODS].sort((a, b) => fnv(`${workstream}\0${wave}\0${a}`) - fnv(`${workstream}\0${wave}\0${b}`))
  return deck[Math.max(0, ids.indexOf(id)) % deck.length]!
}

// A harness without this state's art in the manifest yet draws the Claude art.
export const avatarArt = (art: string, state: AvatarState, mood: Mood, manifest: Record<string, unknown>) =>
  `${art}_${state}_${mood}_24` in manifest ? art : 'claude'

export const waveView = (status: Status, pinned?: number): View => {
  const numbers = [...new Set(status.items.map(item => item.wave))].sort((a, b) => a - b)
  const itemsOf = (wave: number) => status.items.filter(item => item.wave === wave)
  const isDone = (wave: number) => itemsOf(wave).every(item => item.state === 'complete')

  // The lowest unfinished Wave; the last one once all are complete.
  const current = numbers.find(wave => !isDone(wave)) ?? numbers.at(-1) ?? 1
  const waves: Wave[] = numbers.map(wave => ({
    wave,
    complete: itemsOf(wave).filter(item => item.state === 'complete').length,
    total: itemsOf(wave).length,
    kind: isDone(wave) ? 'complete' : wave === current ? 'current' : 'upcoming',
  }))

  // The anchor is the last completed Wave below the current one, Wave 1 before any finish.
  const done = waves.filter(w => w.kind === 'complete' && w.wave <= current)
  const from = Math.max(0, waves.findIndex(w => w.wave === (done.at(-1)?.wave ?? numbers[0])))
  const rest = waves.slice(from)
  const slots: Slot[] =
    rest.length > MAX_SLOTS
      ? [...rest.slice(0, MAX_SLOTS - 1), { more: rest.length - (MAX_SLOTS - 1) }]
      : rest

  // A pin on a Wave that no longer exists falls back to the current one.
  const shown = pinned !== undefined && numbers.includes(pinned) ? pinned : current
  const items = itemsOf(shown)
  return {
    workstream: status.workstream,
    slots,
    current,
    shown,
    // A failed item draws red in the In Progress lane; it still holds its Wave open.
    failed: items.filter(item => item.state === 'failed'),
    todo: items.filter(item => item.state === 'todo'),
    inProgress: items.filter(item => item.state === 'in_progress'),
    reviewing: items.filter(item => item.state === 'reviewing'),
    complete: items.filter(item => item.state === 'complete'),
  }
}

// The ambient signals of the "D · Ambient signals" artboard, from one _status.json.
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
export const allComplete = (status: Status) => status.items.length > 0 && status.items.every(item => item.state === 'complete')

// One key per state that earns a toast, with the toast's text. A key that leaves
// and comes back (a retried item failing again) is a new change. A complete Work
// Item is a merged PR here, as in spinnerWord, so the count is the item count.
export const toastStates = (status: Status) => {
  const all = allComplete(status)
  const out: { key: string; text: string }[] = []
  for (const wave of [...new Set(status.items.map(item => item.wave))].sort((a, b) => a - b)) {
    const items = status.items.filter(item => item.wave === wave)
    // All merged speaks for the last Wave.
    if (!all && items.every(item => item.state === 'complete')) out.push({ key: `wave-${wave}`, text: `Wave ${wave} complete: ${plural(items.length, 'PR')} merged` })
  }
  for (const item of status.items) {
    if (item.state === 'failed') out.push({ key: `failed-${item.id}`, text: `${item.title} failed: ${item.reason ?? 'no reason given'}` })
  }
  if (all) out.push({ key: 'all', text: `All Waves merged: ${plural(status.items.length, 'PR')}` })
  return out
}

const progress = (status: Status) => {
  const { current } = waveView(status)
  const items = status.items.filter(item => item.wave === current)
  return { current, complete: items.filter(item => item.state === 'complete').length, total: items.length }
}

// `orca valkey-opensearch-fixes W2 2/4 · 1 failed`
export const statusLine = (status: Status) => {
  const { current, complete, total } = progress(status)
  const failed = status.items.filter(item => item.state === 'failed').length
  return `orca ${status.workstream} W${current} ${complete}/${total}${failed ? ` · ${failed} failed` : ''}`
}

// `Wave 2 · 2/4 merged`
export const spinnerWord = (status: Status) => {
  const { current, complete, total } = progress(status)
  return `Wave ${current} · ${complete}/${total} merged`
}

// The G Done card's values; a missing `pr`, `startedAt` or `finishedAt` falls back to counts.
export const doneSummary = (status: Status) => {
  const total = status.items.length
  const prs = status.items.map(item => item.pr).filter((pr): pr is number => typeof pr === 'number').sort((a, b) => a - b)
  const range = prs.length === 1 ? `#${prs[0]}` : `#${prs[0]} to #${prs.at(-1)}`
  const merged = prs.length ? `${prs.length} of ${plural(total, 'PR')}: ${range}` : `${total} of ${plural(total, 'Work Item')} complete`
  const ms = Date.parse(status.finishedAt ?? '') - Date.parse(status.startedAt ?? '')
  const minutes = Math.round(ms / 60000)
  const took = Number.isFinite(ms) && ms >= 0 ? (minutes < 60 ? `${minutes}m` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`) : undefined
  return { merged, badge: took ? `Done · ${took}` : 'Done' }
}

// What `/orca-execute copy` puts on the clipboard: each Wave, its Work Items with state and PR, and its progress.
const STATE_WORD = { todo: 'to do', in_progress: 'in progress', reviewing: 'reviewing', complete: 'complete', failed: 'failed' } as const
export const runMarkdown = (status: Status) => {
  const lines = [`# ${status.workstream}`, '', statusLine(status)]
  for (const wave of [...new Set(status.items.map(item => item.wave))].sort((a, b) => a - b)) {
    const items = status.items.filter(item => item.wave === wave)
    lines.push('', `## Wave ${wave}: ${items.filter(item => item.state === 'complete').length}/${items.length} complete`, '')
    for (const item of items) {
      const reason = item.state === 'failed' ? `: ${item.reason ?? 'no reason given'}` : ''
      lines.push(`- ${item.title}: ${STATE_WORD[item.state]}${reason}${typeof item.pr === 'number' ? ` (#${item.pr})` : ''}`)
    }
  }
  return `${lines.join('\n')}\n`
}
