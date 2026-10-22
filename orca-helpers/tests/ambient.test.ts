import { describe, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { OWNER, own } from './own.ts'
import { pngRead } from './png'

const item = (id: string, title: string, wave: number, state: string, extra = {}) => ({ id, title, wave, state, reason: null, ...extra })
const STATUS = {
  workstream: 'Workstream Name',
  active: true,
  items: [item('a', 'Skeleton', 1, 'in_progress'), item('b', 'Validation', 2, 'todo'), item('c', 'Docs', 2, 'todo')],
}
const BAND = {
  step: 'basics', ended: false, updatedAt: new Date().toISOString(),
  steps: [{ id: 'basics', title: 'Basics', state: 'active', answers: {} }],
  checklist: [],
}

// One Workstream under .orca/prompts whose _status.json is `file.status` as it stands now.
const world = (on: On, file: { status?: any; band?: object }) => {
  on('fs.list', async () => ({ value: [{ name: 'ws', kind: 'dir', size: 0, mtimeMs: 0, isLink: false }] }) as never)
  on('fs.read', async ($, e) => {
    if (e.path.endsWith('.owner')) return { value: OWNER }
    if (file.status && e.path.endsWith('ws/_status.json')) return { value: JSON.stringify(file.status) }
    if (file.band && e.path.endsWith('.orca/prompts/_prompt-band.json')) return { value: JSON.stringify(file.band) }
    if (e.path.endsWith('.png')) return pngRead(e.path)
    throw new Error(`ENOENT ${e.path}`)
  })
  on('session.start', async ($, e) => ({ cwd: e.cwd }))
  on('command.register', async () => ({ value: undefined }) as never)
  on('env.get', async () => ({ value: undefined }) as never)
  on('session.turns', async () => ({ value: 1 }) as never)
  on('config.list', async () => ({ value: [] }) as never)
  on('ui.render', { component: 'AbovePrompt' }, ($, e) => h($.ui.resolve(e).Text, {}, 'engine band') as never)
  on('ui.render', { component: 'AskUserQuestion' }, () => ({ type: 'engine', ref: 0 }) as never)
  on('ui.render', { component: 'Spinner' }, ($, e) => h($.ui.resolve(e).Text, {}, `word: ${e.props.word}`) as never)
  return mock.clock(on)
}
const start = { cwd: '/repo', surface: 'terminal', isInteractive: true } as const
const above = ($: any) =>
  $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 30, bodyColumns: 120 } } as never)
const spinner = ($: any) =>
  $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', component: 'Spinner', props: { word: 'Sauteing', message: null, suffix: '…', mode: 'thinking' } } as never)
const QUESTION = { tool: 'AskUserQuestion', questions: [{ question: 'Which?', header: 'Pick', multiSelect: false, options: [{ label: 'a', description: 'a' }, { label: 'b', description: 'b' }] }] }

describe('Owning Session', () => {
  test('a non-owner session draws no band, strip, toast, status line entry or Spinner word', async ($, on) => {
    const env = own(on)
    env.session = 'session-b'
    const file = { status: structuredClone(STATUS), band: BAND }
    const clock = world(on, file)
    await $.session.start(start)
    const band = await above($)
    expect(await band.find({ type: 'Text', text: 'engine band' })).toBeDefined()
    expect(await band.find({ type: 'Text', text: 'Orca Prompt' })).toBeUndefined()
    expect(await band.find({ type: 'Text', text: 'Workstream Name' })).toBeUndefined()
    const strip = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', component: 'AskUserQuestion', props: QUESTION } as never)
    expect(await strip.find({ type: 'Text', text: 'Orca Prompt' })).toBeUndefined()
    const spin = await spinner($)
    expect(await spin.find({ type: 'Text', text: 'word: Sauteing' })).toBeDefined()
    file.status.items[0].state = 'complete'
    await clock.advance(2000)
    expect(env.toasts).toEqual([])
    expect(env.status.filter(Boolean)).toEqual([])
    await Promise.all([band.unmount(), strip.unmount(), spin.unmount()])
  })
})

describe('ambient signals', () => {
  test('each toast fires once per change', async ($, on) => {
    const env = own(on)
    const file = { status: structuredClone(STATUS) }
    const clock = world(on, file)
    await $.session.start(start)
    // The first sight of a Workstream sets its states without a toast.
    expect(env.toasts).toEqual([])
    file.status.items[0].state = 'complete'
    await clock.advance(2000)
    await clock.advance(2000)
    expect(env.toasts).toEqual(['Wave 1 complete: 1 PR merged'])
    Object.assign(file.status.items[1], { state: 'failed', reason: 'tests red' })
    await clock.advance(2000)
    await clock.advance(2000)
    expect(env.toasts.at(-1)).toBe('Validation failed: tests red')
    // A retry that fails again is a new change.
    file.status.items[1].state = 'in_progress'
    await clock.advance(2000)
    file.status.items[1].state = 'failed'
    await clock.advance(2000)
    expect(env.toasts.filter(t => t.startsWith('Validation failed'))).toHaveLength(2)
    for (const i of file.status.items) i.state = 'complete'
    await clock.advance(2000)
    expect(env.toasts.at(-1)).toBe('All Waves merged: 3 PRs')
    expect(env.toasts).toHaveLength(4)
  })

  test('overlapping polls toast a change once', async ($, on) => {
    const env = own(on)
    const file = { status: structuredClone(STATUS) }
    const clock = world(on, file)
    await $.session.start(start)
    file.status.items[0].state = 'complete'
    // Two ticks land while the first poll is still running.
    await Promise.all([clock.advance(2000), clock.advance(2000)])
    await clock.advance(2000)
    expect(env.toasts).toHaveLength(1)
  })

  test('regaining ownership repeats no toast from while away', async ($, on) => {
    const env = own(on)
    const file = { status: structuredClone(STATUS) }
    const clock = world(on, file)
    await $.session.start(start)
    env.session = 'session-b'
    file.status.items[0].state = 'complete'
    await clock.advance(2000)
    env.session = OWNER
    await clock.advance(2000)
    expect(env.toasts).toEqual([])
  })

  test('a reload repeats no toast', async ($, on) => {
    // The module before the reload saw Wave 1 complete and toasted it.
    const env = own(on, { workstream: 'Workstream Name', keys: ['wave-1'] })
    const status = structuredClone(STATUS)
    status.items[0].state = 'complete'
    const clock = world(on, { status })
    await $.session.start(start)
    await clock.advance(2000)
    expect(env.toasts).toEqual([])
  })

  test('the status line entry follows the current Wave and clears on --stop', async ($, on) => {
    const env = own(on)
    const file = { status: structuredClone(STATUS) }
    const clock = world(on, file)
    await $.session.start(start)
    expect(env.status.at(-1)).toBe('orca Workstream Name W1 0/1')
    file.status.items[0].state = 'complete'
    Object.assign(file.status.items[1], { state: 'failed', reason: 'tests red' })
    await clock.advance(2000)
    expect(env.status.at(-1)).toBe('orca Workstream Name W2 0/2 · 1 failed')
    // set_status.py --stop clears `active`.
    file.status.active = false
    await clock.advance(2000)
    expect(env.status.at(-1)).toBeUndefined()
  })

  test('the Spinner word reads the current Wave', async ($, on) => {
    own(on)
    const status = structuredClone(STATUS)
    status.items[0].state = 'complete'
    status.items[1].state = 'complete'
    world(on, { status })
    await $.session.start(start)
    const spin = await spinner($)
    expect(await spin.find({ type: 'Text', text: 'word: Wave 2 · 1/2 merged' })).toBeDefined()
    await spin.unmount()
  })
})

describe('Done tab', () => {
  const done = (extra = {}) => ({ ...STATUS, items: STATUS.items.map(i => ({ ...i, state: 'complete' })), ...extra })

  test('opens by itself once every Work Item is complete, with the G Done card', async ($, on) => {
    own(on)
    const status = done({ startedAt: '2026-10-21T10:00:00Z', finishedAt: '2026-10-21T10:38:00Z' })
    status.items = status.items.map((i, n) => ({ ...i, pr: 161 + n, harness: 'claude' }))
    world(on, { status })
    await $.session.start(start)
    const ui = await above($)
    expect(await ui.find({ type: 'Text', text: ' Done · 38m ' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: '3 of 3 PRs: #161 to #163' })).toBeDefined()
    for (const id of ['a', 'b', 'c']) expect(await ui.find({ type: 'Image', key: `avatar-${id}` })).toBeDefined()
    // A Wave tab shows its columns; the Done tab brings the card back.
    await ui.press({ key: 'wave-2' })
    expect(await ui.find({ type: 'Text', text: 'COMPLETE' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: ' Done · 38m ' })).toBeUndefined()
    await ui.press({ key: 'wave-done' })
    expect(await ui.find({ type: 'Text', text: ' Done · 38m ' })).toBeDefined()
    await ui.unmount()
  })

  test('opens by itself though a Wave tab was pinned', async ($, on) => {
    own(on)
    const file = { status: structuredClone(STATUS) }
    const clock = world(on, file)
    await $.session.start(start)
    const ui = await above($)
    await ui.press({ key: 'wave-1' })
    for (const i of file.status.items) i.state = 'complete'
    await clock.advance(2000)
    expect(await ui.find({ type: 'Text', text: '3 of 3 Work Items complete' })).toBeDefined()
    await ui.unmount()
  })

  test('falls back to counts without pr, startedAt and finishedAt', async ($, on) => {
    own(on)
    world(on, { status: done() })
    await $.session.start(start)
    const ui = await above($)
    expect(await ui.find({ type: 'Text', text: ' Done ' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: '3 of 3 Work Items complete' })).toBeDefined()
    await ui.unmount()
  })

  test('stays away while a Work Item is open', async ($, on) => {
    own(on)
    world(on, { status: STATUS })
    await $.session.start(start)
    const ui = await above($)
    expect(await ui.find({ type: 'Text', text: 'Done' })).toBeUndefined()
    await ui.unmount()
  })
})
