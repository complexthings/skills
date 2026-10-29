import { describe, expect, test } from 'claude-code/testing'

import { MOODS, avatarArt, avatarMood, avatarState, runMarkdown, waveView } from '../hooks/waves.ts'
import type { Item, Slot, State } from '../hooks/waves.ts'

// A Workstream with `sizes[i]` items in Wave i+1, the first `done` Waves complete.
const status = (sizes: number[], done = 0, set: Record<string, State> = {}) => ({
  workstream: 'ws',
  active: true,
  items: sizes.flatMap((size, w) =>
    Array.from({ length: size }, (_, i): Item => {
      const id = `w${w + 1}-${i + 1}`
      return { id, title: id, wave: w + 1, state: set[id] ?? (w < done ? 'complete' : 'todo'), reason: null }
    }),
  ),
})
const label = (slot: Slot) => ('more' in slot ? `+${slot.more}` : `${slot.wave}:${slot.kind}`)

describe('waveView', () => {
  test('one Wave shows alone with no pill', () => {
    const view = waveView(status([3]))
    expect(view.slots.map(label)).toEqual(['1:current'])
    expect(view.todo.length).toBe(3)
  })

  test('four Waves fit without a pill', () => {
    const view = waveView(status([2, 2, 2, 2], 1, { 'w2-1': 'in_progress' }))
    expect(view.slots.map(label)).toEqual(['1:complete', '2:current', '3:upcoming', '4:upcoming'])
    expect(view.current).toBe(2)
    expect(view.inProgress.map(i => i.id)).toEqual(['w2-1'])
    expect(view.todo.map(i => i.id)).toEqual(['w2-2'])
  })

  const eight = [
    [0, ['1:current', '2:upcoming', '3:upcoming', '+5']],
    [1, ['1:complete', '2:current', '3:upcoming', '+5']],
    [2, ['2:complete', '3:current', '4:upcoming', '+4']],
    [3, ['3:complete', '4:current', '5:upcoming', '+3']],
    [4, ['4:complete', '5:current', '6:upcoming', '+2']],
    [5, ['5:complete', '6:current', '7:upcoming', '8:upcoming']],
    [6, ['6:complete', '7:current', '8:upcoming']],
    [7, ['7:complete', '8:current']],
    [8, ['8:complete']],
  ] as const
  for (const [done, slots] of eight) {
    test(`eight Waves with ${done} complete`, () => {
      expect(waveView(status([2, 2, 2, 2, 2, 2, 2, 2], done)).slots.map(label)).toEqual([...slots])
    })
  }

  test('every Wave counts complete/total, upcoming ones included', () => {
    const [, , upcoming] = waveView(status([8, 4, 6, 12], 1)).slots
    expect(upcoming).toEqual({ wave: 3, complete: 0, total: 6, kind: 'upcoming' })
  })

  test('a failed item leaves In Progress for the failure row and holds its Wave open', () => {
    const view = waveView(status([1, 2], 0, { 'w1-1': 'failed' }))
    expect(view.current).toBe(1)
    expect(view.slots.map(label)).toEqual(['1:current', '2:upcoming'])
    expect(view.failed.map(i => i.id)).toEqual(['w1-1'])
    expect(view.inProgress).toEqual([])
    expect(view.complete).toEqual([])
  })

  test('a pinned Wave draws its own columns; a pin on a missing Wave falls back', () => {
    const view = waveView(status([1, 2], 1), 1)
    expect(view.current).toBe(2)
    expect(view.shown).toBe(1)
    expect(view.complete.map(i => i.id)).toEqual(['w1-1'])
    expect(waveView(status([1, 2], 1), 9).shown).toBe(2)
  })

  test('all complete shows the last Wave as current', () => {
    const view = waveView(status([2, 3], 2))
    expect(view.current).toBe(2)
    expect(view.slots.map(label)).toEqual(['2:complete'])
    expect(view.complete.length).toBe(3)
    expect(view.todo).toEqual([])
  })
})

describe('Harness Avatar', () => {
  test('each column has its Avatar State, a failed item In Progress', () => {
    expect((['todo', 'in_progress', 'failed', 'reviewing', 'complete'] as State[]).map(avatarState)).toEqual(['todo', 'progress', 'progress', 'progress', 'complete'])
  })

  test('a reviewing item draws in its own lane and holds its Wave open', () => {
    const view = waveView({
      workstream: 'ws',
      active: true,
      items: [
        { id: 'a', title: 'A', wave: 1, state: 'complete' },
        { id: 'b', title: 'B', wave: 1, state: 'reviewing', review: { round: 1, verdict: null, reviewer: 'codex' } },
      ],
    })
    expect(view.current).toBe(1)
    expect(view.reviewing.map(i => i.id)).toEqual(['b'])
    expect([...view.inProgress, ...view.complete].map(i => i.id)).toEqual(['a'])
  })

  test('the Mood is stable, differs inside a Wave, and changes across Waves and workstreams', () => {
    const ids = ['01-a', '02-b', '03-c', '04-d', '05-e', '06-f', '07-g']
    expect(avatarMood('ws', 1, ids, '01-a')).toBe(avatarMood('ws', 1, ids, '01-a'))
    expect(new Set(ids.map(id => avatarMood('ws', 1, ids, id))).size).toBe(MOODS.length)
    const decks = new Set(['ws', 'other', 'third'].flatMap(ws => [1, 2, 3].map(w => ids.map(id => avatarMood(ws, w, ids, id)).join())))
    expect(decks.size).toBeGreaterThan(3)
  })

  test('a harness without state art falls back to the Claude art', () => {
    const manifest = { claude_todo_red_24: {}, pi_todo_red_24: {} }
    expect(avatarArt('pi', 'todo', 'red', manifest)).toBe('pi')
    expect(avatarArt('pi', 'progress', 'red', manifest)).toBe('claude')
    expect(avatarArt('codex', 'todo', 'red', manifest)).toBe('claude')
  })
})

describe('runMarkdown', () => {
  test('a reviewing item reads as reviewing', () => {
    expect(runMarkdown(status([2], 0, { 'w1-1': 'reviewing' }))).toContain('- w1-1: reviewing\n')
  })
})
