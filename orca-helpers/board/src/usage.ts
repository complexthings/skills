// The usage maths the chart and Spend panel share, kept free of React so tests/usage.test.ts can run it.

export type Series = {
  bucketSeconds: number
  start: string
  buckets: number
  models: { model: string; cost: (number | null)[]; tokens: (number | null)[]; seconds: (number | null)[] }[]
}

// The same sizes as BUCKETS and MAX_BUCKETS in skills/orca-board/scripts/board.py.
const BUCKETS = [60, 300, 600, 1800, 3600, 3 * 3600, 6 * 3600, 86400]
export const MAX_BUCKETS = 48

const ok = (s: Series | null | undefined): s is Series => !!s && s.buckets > 0 && Number.isFinite(Date.parse(s.start))
const add = (a: number | null | undefined, b: number | null | undefined) => (a == null && b == null ? null : (a ?? 0) + (b ?? 0))

/**
 * Several Workstreams' `series` on one time grid, or null when none has usage. The bucket size is the
 * smallest of BUCKETS, then whole days, that is a multiple of every source size and keeps MAX_BUCKETS
 * buckets or fewer, so each source bucket lands whole in one merged bucket. Models merge by name.
 */
export function mergeSeries(list: (Series | null | undefined)[]): Series | null {
  const all = list.filter(ok)
  if (all.length < 2) return all[0] ?? null
  const first = Math.min(...all.map(s => Date.parse(s.start) / 1000))
  const end = Math.max(...all.map(s => Date.parse(s.start) / 1000 + s.buckets * s.bucketSeconds))
  const fits = (b: number) => all.every(s => b % s.bucketSeconds === 0) && Math.ceil((end - Math.floor(first / b) * b) / b) <= MAX_BUCKETS
  let size = BUCKETS.find(fits)
  for (let d = 2; size == null; d++) if (fits(d * 86400)) size = d * 86400
  const start = Math.floor(first / size) * size
  const n = Math.ceil((end - start) / size)
  const found = new Map<string, Series['models'][number]>()
  for (const s of all) {
    const from = Date.parse(s.start) / 1000
    for (const m of s.models) {
      const t = found.get(m.model) ?? { model: m.model, cost: Array(n).fill(null), tokens: Array(n).fill(null), seconds: Array(n).fill(null) }
      found.set(m.model, t)
      for (let k = 0; k < s.buckets; k++) {
        const j = Math.floor((from + k * s.bucketSeconds - start) / size)
        t.cost[j] = add(t.cost[j], m.cost[k])
        t.tokens[j] = add(t.tokens[j], m.tokens[k])
        t.seconds[j] = add(t.seconds[j], m.seconds[k])
      }
    }
  }
  const sum = (v: (number | null)[]) => v.reduce<number>((a, x) => a + (x ?? 0), 0)
  const models = [...found.values()].sort((a, b) => sum(b.cost) - sum(a.cost) || sum(b.tokens) - sum(a.tokens) || a.model.localeCompare(b.model))
  return { bucketSeconds: size, start: new Date(start * 1000).toISOString(), buckets: n, models }
}

/** Cost per bucket over every model, null treated as 0. */
export const costPerBucket = (s: Series) => Array.from({ length: s.buckets }, (_, k) => s.models.reduce((a, m) => a + (m.cost[k] ?? 0), 0))

/** USD per hour over the last hour, or the last bucket when buckets are longer; 0 once the run has gone quiet. */
export function burnPerHour(s: Series | null | undefined, now = Date.now()) {
  if (!ok(s)) return 0
  const window = Math.max(3600, s.bucketSeconds) * 1000
  const start = Date.parse(s.start)
  const cost = costPerBucket(s).reduce((a, c, k) => (start + (k + 1) * s.bucketSeconds * 1000 > now - window ? a + c : a), 0)
  return cost / (window / 3600000)
}

/** Local round-hour ticks between `start` and `end` (ms), every 1, 2, 3, 6 or 12 hours or whole days, at most `max`. */
export function hourTicks(start: number, end: number, max = 6) {
  const hours: Date[] = []
  const t = new Date(start)
  t.setMinutes(0, 0, 0)
  if (t.getTime() < start) t.setHours(t.getHours() + 1)
  for (; t.getTime() <= end; t.setHours(t.getHours() + 1)) hours.push(new Date(t))
  for (const step of [1, 2, 3, 6, 12]) {
    const picked = hours.filter(d => d.getHours() % step === 0)
    if (picked.length <= max) return picked
  }
  const days = hours.filter(d => d.getHours() === 0)
  const every = Math.ceil(days.length / max)
  return days.filter((_, i) => i % every === 0)
}

/**
 * Today's pace from `s`: today is the local calendar day of `now`, midnight to the next midnight, never
 * the newest bucket. A bucket that started before midnight counts only the share of it after midnight.
 * `steps` are the cumulative spend per bucket, `projected` adds burnPerHour() times the hours left, and
 * `cross` is when the projection reaches `budget` (now if already over), else null.
 */
export function todayPace(s: Series | null | undefined, budget: number | null = null, now = Date.now()) {
  const day = new Date(now)
  day.setHours(0, 0, 0, 0)
  const start = day.getTime()
  day.setDate(day.getDate() + 1)
  const end = day.getTime()
  const steps: { from: number; to: number; v: number }[] = []
  const models = new Map<string, number>()
  let spent = 0
  if (ok(s)) {
    const ms = s.bucketSeconds * 1000
    const first = Date.parse(s.start)
    for (let k = 0; k < s.buckets; k++) {
      const from = first + k * ms
      const share = Math.min(1, Math.max(0, (from + ms - start) / ms))
      if (!share || from >= now) continue
      for (const m of s.models) models.set(m.model, (models.get(m.model) ?? 0) + (m.cost[k] ?? 0) * share)
      spent = [...models.values()].reduce((a, c) => a + c, 0)
      steps.push({ from: Math.max(from, start), to: Math.min(from + ms, now), v: spent })
    }
  }
  const projected = spent + burnPerHour(s, now) * ((end - now) / 3600000)
  const cross = budget == null ? null : spent >= budget ? now : projected > budget ? now + ((budget - spent) / (projected - spent)) * (end - now) : null
  return { start, end, now, spent, projected, cross, steps, models: [...models].map(([model, cost]) => ({ model, cost })).filter(m => m.cost > 0).sort((a, b) => b.cost - a.cost) }
}
