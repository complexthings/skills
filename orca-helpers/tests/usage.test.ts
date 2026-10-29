import { describe, expect, test } from 'claude-code/testing'

import { MAX_BUCKETS, burnPerHour, hourTicks, mergeSeries } from '../board/src/usage.ts'
import type { Series } from '../board/src/usage.ts'

const SIZES = [60, 300, 600, 1800, 3600, 10800, 21600, 86400, 172800]

// A series as board.py builds it: start floored to the bucket size, one model with `cost` per bucket.
const series = (startSec: number, size: number, cost: number[], model = 'm'): Series => ({
  bucketSeconds: size,
  start: new Date(Math.floor(startSec / size) * size * 1000).toISOString(),
  buckets: cost.length,
  models: [{ model, cost, tokens: cost.map(c => c * 1000), seconds: cost.map(() => 60) }],
})
const total = (s: Series) => s.models.reduce((a, m) => a + m.cost.reduce<number>((b, c) => b + (c ?? 0), 0), 0)

describe('mergeSeries', () => {
  test('null and empty inputs give null; one series comes back as is', () => {
    expect(mergeSeries([])).toBe(null)
    expect(mergeSeries([null, undefined])).toBe(null)
    const one = series(1_700_000_000, 600, [1, 2])
    expect(mergeSeries([null, one])).toBe(one)
  })

  test('models merge by name and sort by cost', () => {
    const a = series(1_700_000_000, 600, [1, 0], 'small')
    const b = series(1_700_000_600, 600, [5], 'big')
    const c = series(1_700_000_000, 600, [2], 'small')
    const m = mergeSeries([a, b, c])!
    expect(m.models.map(x => x.model)).toEqual(['big', 'small'])
    expect(total(m)).toBe(8)
  })

  // A bound gets a test over the whole input range: random pairs of runs, near and far apart.
  test('every merge keeps at most MAX_BUCKETS buckets, every cost, and whole source buckets', () => {
    let seed = 7
    const rand = () => ((seed = (seed * 1103515245 + 12345) % 2 ** 31) / 2 ** 31)
    for (let i = 0; i < 400; i++) {
      const parts = Array.from({ length: 2 + Math.floor(rand() * 3) }, () => {
        const size = SIZES[Math.floor(rand() * SIZES.length)]!
        const n = 1 + Math.floor(rand() * MAX_BUCKETS)
        return series(1_700_000_000 + Math.floor(rand() * 90 * 86400), size, Array.from({ length: n }, () => Math.round(rand() * 100) / 100))
      })
      const m = mergeSeries(parts)!
      expect(m.buckets).toBeLessThanOrEqual(MAX_BUCKETS)
      expect(m.buckets).toBeGreaterThan(0)
      for (const p of parts) expect(m.bucketSeconds % p.bucketSeconds).toBe(0)
      expect(Math.abs(total(m) - parts.reduce((a, p) => a + total(p), 0))).toBeLessThan(1e-6)
      for (const x of m.models) expect(x.cost.length).toBe(m.buckets)
    }
  })
})

describe('burnPerHour', () => {
  test('counts the last hour only, and nothing once the run is quiet', () => {
    const start = 1_700_000_000
    const s = series(start, 600, [1, 1, 1, 1, 1, 1, 1, 1])
    const end = Date.parse(s.start) + 8 * 600_000
    expect(burnPerHour(s, end)).toBe(6)
    expect(burnPerHour(s, end + 5 * 3_600_000)).toBe(0)
    expect(burnPerHour(null)).toBe(0)
  })
})

describe('hourTicks', () => {
  test('lands on round hours, at most max ticks, for spans from minutes to weeks', () => {
    const t0 = 1_700_000_123_000
    for (const span of [30 * 60_000, 3 * 3_600_000, 11 * 3_600_000, 30 * 3_600_000, 20 * 86_400_000]) {
      const ticks = hourTicks(t0, t0 + span)
      expect(ticks.length).toBeLessThanOrEqual(6)
      for (const d of ticks) {
        expect(d.getMinutes()).toBe(0)
        expect(d.getTime() >= t0 && d.getTime() <= t0 + span).toBe(true)
      }
    }
  })
})
