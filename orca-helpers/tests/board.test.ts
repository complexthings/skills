import { describe, expect, test } from 'claude-code/testing'

import { repoSpend, waveFilter, type Repo, type Workstream } from '../board/src/types.ts'
import { mergeSeries, todayPace, type Series } from '../board/src/usage.ts'

const ws = (active: boolean) =>
  ({ active, waves: [1, 2, 3].map(n => ({ n, title: `w${n}`, state: active && n === 3 ? 'active' : 'complete', startedAt: null, totals: null, items: [] })) }) as unknown as Workstream

describe('waveFilter', () => {
  test('a running lane keeps its Active Wave filter', () => {
    expect(waveFilter('active', ws(true))).toBe('active')
  })

  test('a lane whose Workstream finishes drops a stale Active Wave filter for All Waves', () => {
    expect(waveFilter('active', ws(false))).toBe('all')
  })

  test('a chosen Wave and All Waves pass through', () => {
    expect(waveFilter('2', ws(false))).toBe('2')
    expect(waveFilter('all', ws(true))).toBe('all')
  })

  test('the Status Page pins the active Wave', () => {
    expect(waveFilter('all', ws(true), true)).toBe('active')
  })
})

describe('todayPace', () => {
  const noon = new Date(2026, 9, 26, 12).getTime()
  const H = 3600000
  const series = (start: number, size: number, cost: number[]): Series => ({
    bucketSeconds: size,
    start: new Date(start).toISOString(),
    buckets: cost.length,
    models: [{ model: 'm', cost, tokens: cost.map(() => 0), seconds: cost.map(() => 0) }],
  })

  test('a series whose newest bucket is from yesterday spends $0 today', () => {
    const p = todayPace(series(noon - 30 * H, 3600, [5, 7]), 10, noon)
    expect(p.spent).toBe(0)
    expect(p.projected).toBe(0)
    expect(p.steps).toEqual([])
    expect(p.cross).toBe(null)
    expect(p.start).toBe(new Date(2026, 9, 26).getTime())
    expect(p.end).toBe(new Date(2026, 9, 27).getTime())
  })

  test('a known burn rate projects to the next local midnight and crosses the budget there', () => {
    // Six 10-minute buckets of $1/3 end at noon: $2 spent, $2 an hour, 12 hours left.
    const p = todayPace(series(noon - H, 600, Array(6).fill(1 / 3)), 14, noon)
    expect(Math.abs(p.spent - 2)).toBeLessThan(1e-9)
    expect(Math.abs(p.projected - 26)).toBeLessThan(1e-9)
    expect(Math.abs(p.cross! - new Date(2026, 9, 26, 18).getTime())).toBeLessThan(1000)
    expect(todayPace(series(noon - H, 600, Array(6).fill(1 / 3)), 1, noon).cross).toBe(noon)
  })

  test('a bucket that spans midnight counts only its share after midnight', () => {
    const p = todayPace(series(new Date(2026, 9, 25, 23).getTime(), 7200, [2]), null, noon)
    expect(Math.abs(p.spent - 1)).toBeLessThan(1e-9)
    expect(p.steps[0]!.from).toBe(new Date(2026, 9, 26).getTime())
  })

  test('the drawn total projection crosses the budget even when the spend is in an unbudgeted Workstream', () => {
    // Budgeted A: $1.10 today, $0.10 in the last hour. Unbudgeted B: $5 in the last hour. Budget $10.
    const a = series(noon - 6 * H, 3600, [1, 0, 0, 0, 0, 0.1])
    const total = mergeSeries([a, series(noon - H, 600, Array(6).fill(5 / 6))])
    const p = todayPace(total, 10, noon)
    expect(Math.abs(p.spent - 6.1)).toBeLessThan(1e-9)
    expect(Math.abs(p.projected - 67.3)).toBeLessThan(1e-9)
    expect(Math.abs(p.cross! - (noon + (3.9 / 5.1) * H))).toBeLessThan(1000)
    // The dashed line from (now, spent) to (end, projected) is at the budget at the crossing time.
    expect(Math.abs(p.spent + (p.projected - p.spent) * ((p.cross! - p.now) / (p.end - p.now)) - 10)).toBeLessThan(1e-9)
    expect(todayPace(a, 10, noon).cross).toBe(null)
  })
})

describe('repoSpend', () => {
  const spendWs = (cost: number, budgetUsd: number | null) => ({ totals: { cost }, budgetUsd }) as unknown as Workstream
  const repo = (...workstreams: Workstream[]) => ({ workstreams }) as unknown as Repo

  test('unbudgeted spend stays out of the budget meter: $5 of $10 budgeted plus $20 unbudgeted is $5 / $10', () => {
    expect(repoSpend(repo(spendWs(5, 10), spendWs(20, null)))).toEqual({ spent: 5, budget: 10 })
  })

  test('with no budget at all, spent is the whole repo', () => {
    expect(repoSpend(repo(spendWs(5, null), spendWs(20, null)))).toEqual({ spent: 25, budget: null })
  })
})
