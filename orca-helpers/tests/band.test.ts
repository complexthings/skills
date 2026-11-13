import { describe, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { OWNER, own } from './own.ts'

import { cellsRead, file as pngFile, pngRead } from './png'

// The avatar manifest as export.mjs writes it: Claude in every state, Pi in Todo only.
const MANIFEST = Object.fromEntries(
  ['todo', 'progress', 'complete'].flatMap(state =>
    ['default', 'red', 'blue', 'green', 'yellow', 'purple', 'teal'].map(mood => [`claude_${state}_${mood}_24`, { frames: state === 'todo' ? 1 : 4 }]),
  ),
)
MANIFEST.pi_todo_default_24 = { frames: 1 }

const STATUS = {
  workstream: 'Workstream Name',
  active: true,
  items: [
    { id: 'a', title: 'Skill Skeleton', wave: 1, state: 'complete', reason: null },
    { id: 'b', title: 'Harness Detection', wave: 2, state: 'complete', reason: null },
    { id: 'c', title: 'Prompt Scaffolding', wave: 2, state: 'in_progress', reason: null },
    { id: 'd', title: 'Validation', wave: 2, state: 'failed', reason: 'tests red' },
    { id: 'e', title: 'Docs', wave: 3, state: 'todo', reason: null },
  ],
}

// One Workstream directory under .orca/prompts holding `status`, if any.
const world = (on: On, status?: object, vars: Record<string, string> = {}) => {
  on('fs.list', async () => ({ value: [{ name: 'ws', kind: 'dir', size: 0, mtimeMs: 0, isLink: false }] }) as never)
  on('fs.read', async ($, e) => {
    if (e.path.endsWith('.owner')) return { value: OWNER }
    if (status && e.path.endsWith('ws/_status.json')) return { value: JSON.stringify(status) }
    if (e.path.endsWith('avatars/manifest.json')) return { value: JSON.stringify(MANIFEST) }
    if (e.path.endsWith('.png')) return pngRead(e.path)
    if (e.path.endsWith('.cells')) return cellsRead(e.path)
    throw new Error(`ENOENT ${e.path}`)
  })
  on('session.start', async ($, e) => ({ cwd: e.cwd }))
  on('command.register', async () => ({ value: undefined }) as never)
  on('env.get', async ($, e) => ({ value: vars[e.name] }) as never)
  on('session.turns', async () => ({ value: 0 }) as never)
  on('config.list', async () => ({ value: [] }) as never)
  // The engine's own band, drawn when the plugin hands the site on.
  on('ui.render', { component: 'AbovePrompt' }, ($, e) => h($.ui.resolve(e).Text, {}, 'engine band') as never)
  return mock.clock(on)
}
const start = { cwd: '/repo', surface: 'terminal', isInteractive: true } as const
const BAND = {
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 20, bodyColumns: 100 },
} as never

describe('wave band', () => {
  for (const surface of ['terminal', 'desktop'] as const) {
    test(`${surface}: draws the active Workstream and collapses on the caret`, async ($, on) => {
      own(on)
      world(on, STATUS)
      await $.session.start(start)
      const ui = await $.ui.mount({ plugin: 'orca-helpers', surface, ...(BAND as object) } as never)

      expect(await ui.find({ type: 'Text', text: 'Workstream Name' })).toBeDefined()
      const wave = (n: number, c: number, t: number) => (surface === 'terminal' ? `W${n} ${c}/${t}` : `Wave ${n} · ${c}/${t}`)
      const heading = surface === 'terminal' ? 'IN PROGRESS' : 'In progress'
      expect(await ui.find({ type: 'Text', text: wave(1, 1, 1) })).toBeDefined()
      expect(await ui.find({ type: 'Text', text: ` ${wave(2, 1, 3)} ` })).toBeDefined()
      expect(await ui.find({ type: 'Text', text: wave(3, 0, 1) })).toBeDefined()
      expect(await ui.find({ type: 'Text', text: heading })).toBeDefined()
      // The Wave name lives in the top bar only, and no drawn rule remains.
      expect(await ui.find({ type: 'Text', text: /- Wave/ } as never)).toBeUndefined()
      expect(await ui.find({ type: 'Text', text: /─/ } as never)).toBeUndefined()

      await ui.press({ key: 'caret' })
      expect(await ui.find({ type: 'Text', text: heading })).toBeUndefined()
      expect(await ui.find({ type: 'Text', text: 'Workstream Name' })).toBeDefined()
      await ui.unmount()
    })
  }

  test('a failed Work Item stays in the In Progress lane, once, in red with its reason', async ($, on) => {
    own(on)
    world(on, STATUS)
    await $.session.start(start)
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', ...(BAND as object) } as never)
    // Text matches by substring, so one hit means no column draws the title too.
    expect(await ui.findAll({ type: 'Text', text: 'Validation' })).toHaveLength(1)
    expect(await ui.find({ type: 'Text', text: '! Validation: tests red' })).toBeDefined()
    expect(await ui.find({ type: 'Image', key: 'avatar-d' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Prompt Scaffolding' })).toBeDefined()
    await ui.unmount()
  })

  test('an In Progress card with progress draws a bar, done/total and the truncated note', async ($, on) => {
    own(on)
    const note = 'Writing the band tests for the progress bar and its truncated note'
    const items = STATUS.items.map(item => (item.id === 'c' ? { ...item, progress: { done: 2, total: 5, note, at: '2026-10-24T10:00:00+00:00' } } : item))
    // A stale progress on a Complete card draws nothing.
    items[1] = { ...items[1]!, progress: { done: 5, total: 5, note: 'stale', at: '2026-10-24T10:00:00+00:00' } } as never
    world(on, { ...STATUS, items })
    await $.session.start(start)
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', ...(BAND as object) } as never)
    // bodyColumns 100: each column is 31 cells, so the text beside the avatar has 26.
    expect(await ui.find({ type: 'Text', text: ' 2/5' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: '━'.repeat(9) })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: `${note.slice(0, 25)}…` })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'stale' })).toBeUndefined()
    expect(await ui.findAll({ type: 'Text', text: '━' } as never)).toHaveLength(2)
    await ui.unmount()
  })

  test('cards without progress draw no bar', async ($, on) => {
    own(on)
    world(on, STATUS)
    await $.session.start(start)
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', ...(BAND as object) } as never)
    expect(await ui.find({ type: 'Text', text: 'Prompt Scaffolding' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /━|^ \d+\/\d+$/ } as never)).toBeUndefined()
    await ui.unmount()
  })

  test('a Wave tab pins its columns and a second press returns to the current Wave', async ($, on) => {
    own(on)
    world(on, STATUS)
    await $.session.start(start)
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', ...(BAND as object) } as never)
    expect(await ui.find({ type: 'Text', text: 'Prompt Scaffolding' })).toBeDefined()

    await ui.press({ key: 'wave-1' })
    expect(await ui.find({ type: 'Text', text: 'Skill Skeleton' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Prompt Scaffolding' })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: ' W1 1/1 ' })).toBeDefined()

    await ui.press({ key: 'wave-1' })
    expect(await ui.find({ type: 'Text', text: 'Prompt Scaffolding' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Skill Skeleton' })).toBeUndefined()
    await ui.unmount()
  })

  test('terminal: draws the picked icons as PNG frames with the glyphs as alt', async ($, on) => {
    own(on)
    const clock = world(on, STATUS)
    await $.session.start(start)
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', ...(BAND as object) } as never)

    const file = (key: string) => pngFile(ui, key)
    expect(await file('icon-1')).toMatch(/\/hooks\/assets\/check_0\.png$/)
    expect(await file('icon-3')).toMatch(/\/hooks\/assets\/upcoming_0\.png$/)
    expect((await ui.find({ type: 'Image', key: 'icon-1' }))!.props.alt).toBe('✔ ')

    const wave = await file('icon-2')
    expect(wave).toMatch(/\/hooks\/assets\/wave_\d\.png$/)
    await clock.advance(400)
    expect(await file('icon-2')).not.toBe(wave)
    await ui.unmount()
  })

  test('desktop: draws the picked icons as SVG rects', async ($, on) => {
    own(on)
    world(on, STATUS)
    await $.session.start(start)
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'desktop', ...(BAND as object) } as never)
    const svgs = await ui.findAll({ type: 'Svg' })
    expect(svgs.map(s => s.props.alt)).toEqual(['orca', 'complete', 'current', 'upcoming'])
    for (const s of svgs) expect(s.props.source).toMatch(/^<svg [^>]*><rect /)
    await ui.unmount()
  })

  test('terminal: draws the orca icon and each Work Item\'s Harness Avatar in its column state', async ($, on) => {
    own(on)
    world(on, {
      ...STATUS,
      items: [
        { id: 'c', title: 'Prompt Scaffolding', wave: 2, state: 'in_progress', reason: null, harness: 'claude' },
        { id: 'q', title: 'Pi Done', wave: 2, state: 'complete', reason: null, harness: 'pi' },
        { id: 'old', title: 'No Harness', wave: 2, state: 'todo', reason: null },
        { id: 'y', title: 'Pi Todo', wave: 2, state: 'todo', reason: null, harness: 'pi' },
      ],
    })
    await $.session.start(start)
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', ...(BAND as object) } as never)
    const file = (key: string) => pngFile(ui, key)

    expect(await file('icon-orca')).toMatch(/\/hooks\/assets\/orca_\d\.png$/)
    expect(await file('avatar-c')).toMatch(/\/avatars\/claude_progress_[a-z]+_24_\d\.png$/)
    expect(await file('avatar-q')).toMatch(/\/avatars\/claude_complete_[a-z]+_24_\d\.png$/)
    expect(await file('avatar-old')).toMatch(/\/avatars\/claude_todo_[a-z]+_24_0\.png$/)
    // Pi has Todo art in only the default Mood; Wave 2 of this workstream deals it to the fourth item, 'y'.
    expect(await file('avatar-y')).toMatch(/\/avatars\/pi_todo_default_24_0\.png$/)
    await ui.unmount()
  })

  test("a reviewing Work Item draws in the Reviewing column with the reviewer's Harness Avatar beside the author's", async ($, on) => {
    own(on)
    world(on, {
      ...STATUS,
      items: [
        { id: 'c', title: 'Prompt Scaffolding', wave: 2, state: 'in_progress', reason: null, harness: 'claude' },
        { id: 'r', title: 'Under Review', wave: 2, state: 'reviewing', reason: null, harness: 'claude', review: { round: 2, verdict: null, reviewer: 'pi' } },
      ],
    })
    await $.session.start(start)
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', ...(BAND as object) } as never)
    expect(await ui.find({ type: 'Text', text: 'REVIEWING' })).toBeDefined()
    expect(await ui.findAll({ type: 'Text', text: 'Under Review' })).toHaveLength(1)
    expect(await pngFile(ui, 'avatar-r')).toMatch(/\/avatars\/claude_progress_[a-z]+_24_\d\.png$/)
    // Pi has no progress art yet, so its reviewer avatar falls back to the Claude art.
    expect(await pngFile(ui, 'reviewer-r')).toMatch(/\/avatars\/claude_progress_[a-z]+_24_\d\.png$/)
    expect(await ui.find({ type: 'Image', key: 'reviewer-c' })).toBeUndefined()
    await ui.unmount()
  })

  test('a run without a review round draws no Reviewing column', async ($, on) => {
    own(on)
    world(on, STATUS)
    await $.session.start(start)
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', ...(BAND as object) } as never)
    expect(await ui.find({ type: 'Text', text: 'IN PROGRESS' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'REVIEWING' })).toBeUndefined()
    await ui.unmount()
  })

  // TERM_PROGRAM=Orca without CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1: pictures are off (hooks/images.ts).
  for (const off of [true, false]) {
    test(`terminal, pictures ${off ? 'off' : 'on'}: every icon and Harness Avatar draws as ${off ? 'a Raster' : 'an Image'}`, async ($, on) => {
      own(on)
      world(on, STATUS, off ? { TERM_PROGRAM: 'Orca' } : {})
      await $.session.start(start)
      const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', ...(BAND as object) } as never)
      const sizes = { 'icon-orca': [4, 2], 'icon-1': [2, 1], 'icon-2': [2, 1], 'icon-3': [2, 1], 'avatar-b': [4, 2], 'avatar-c': [4, 2], 'avatar-d': [4, 2] }
      for (const [key, size] of Object.entries(sizes)) {
        const raster = await ui.find({ type: 'Raster', key })
        const image = await ui.find({ type: 'Image', key })
        expect(raster === undefined).toBe(!off)
        expect(image === undefined).toBe(off)
        const drawn = (raster ?? image)!
        expect([drawn.props.columns, drawn.props.rows]).toEqual(size)
      }
      if (off) {
        expect(await ui.findAll({ type: 'Image' })).toEqual([])
        for (const alt of ['✔ ', '● ', '🐋']) expect(await ui.find({ type: 'Text', text: alt })).toBeUndefined()
      }
      await ui.unmount()
    })
  }

  test('terminal: the Workstream name and every Wave tab share one row beside the orca', async ($, on) => {
    own(on)
    world(on, STATUS)
    await $.session.start(start)
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', ...(BAND as object) } as never)
    // The name, the separator and the tabs sit in one row Box with only 1-row icons, and the
    // 2-row orca sits outside it, so the row centers beside the orca as a unit.
    const row = (await ui.find({ type: 'Box', key: 'header-row' }))!
    expect(row.text).toBe('Workstream Name│W1 1/1 W2 1/3 W3 0/1')
    expect([row.props.flexDirection, row.props.flexWrap]).toEqual([undefined, undefined])
    const tall = (node: any): boolean => (node.props?.rows ?? 1) > 1 || (node.children ?? []).some(tall)
    expect(tall(row)).toBe(false)
    expect((await ui.find({ type: 'Image', key: 'icon-orca' }))!.props.rows).toBe(2)
    await ui.unmount()
  })

  test('Board dispatches /orca-board, Copy copies the run, each keyboard reachable', async ($, on) => {
    const env = own(on)
    world(on, STATUS)
    const ran: string[] = []
    const copies: string[] = []
    // /orca-board's skill, and the clipboard.
    on('command.run', { command: 'orca-board' }, async ($, e) => { ran.push(e.command); return { text: '' } })
    on('ui.copy', (async ($: any, e: any) => { copies.push(e.text); return { value: { isCopied: true } } }) as never)
    await $.session.start(start)
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', ...(BAND as object) } as never)
    expect((await ui.find({ type: 'Button', key: 'board' }))!.props.hotkey).toBe('b')
    expect((await ui.find({ type: 'Button', key: 'copy' }))!.props.hotkey).toBe('c')

    await ui.press({ key: 'board' })
    await ui.press({ key: 'copy' })
    expect(ran).toEqual(['orca-board'])
    // Copy runs the typed /orca-execute copy's code: the clipboard gets the run, and a toast confirms.
    expect(copies).toHaveLength(1)
    expect(copies[0]).toMatch(/^# Workstream Name\n/)
    expect(env.toasts).toContain('Copied Workstream Name as Markdown.')
    await ui.unmount()
  })

  test('/orca-execute copy puts the run on the clipboard as Markdown and toasts', async ($, on) => {
    const env = own(on)
    world(on, { ...STATUS, items: STATUS.items.map(i => (i.id === 'a' ? { ...i, pr: 12 } : i)) })
    const copies: string[] = []
    on('ui.copy', (async ($: any, e: any) => { copies.push(e.text); return { value: { isCopied: true } } }) as never)
    await $.session.start(start)
    const result = await $.command.run({ command: 'orca-execute', args: 'copy' })
    expect(copies).toEqual([
      [
        '# Workstream Name',
        '',
        'orca Workstream Name W2 1/3 · 1 failed',
        '',
        '## Wave 1: 1/1 complete',
        '',
        '- Skill Skeleton: complete (#12)',
        '',
        '## Wave 2: 1/3 complete',
        '',
        '- Harness Detection: complete',
        '- Prompt Scaffolding: in progress',
        '- Validation: failed: tests red',
        '',
        '## Wave 3: 0/1 complete',
        '',
        '- Docs: to do',
        '',
      ].join('\n'),
    ])
    expect(env.toasts).toContain('Copied Workstream Name as Markdown.')
    expect(result.text).toBe('Copied Workstream Name as Markdown.')
  })

  test('/orca-execute copy that the clipboard refuses returns the Markdown instead', async ($, on) => {
    const env = own(on)
    world(on, STATUS)
    on('ui.copy', async () => ({ value: { isCopied: false, reason: 'no-clipboard' } }) as never)
    await $.session.start(start)
    const result = await $.command.run({ command: 'orca-execute', args: 'copy' })
    expect(env.toasts).toContain('Copy failed: no-clipboard. Run /orca-execute copy to get the Markdown in the transcript.')
    expect(result.text).toContain('## Wave 2: 1/3 complete')
  })

  test('leaves the band to others with no active Workstream', async ($, on) => {
    own(on)
    world(on, { ...STATUS, active: false })
    await $.session.start(start)
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', ...(BAND as object) } as never)
    expect(await ui.find({ type: 'Text', text: 'Workstream Name' })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: 'engine band' })).toBeDefined()
    await ui.unmount()
  })

  test('stays up while a question shows', async ($, on) => {
    own(on)
    world(on, STATUS)
    await $.session.start(start)
    const props = { hasSurvey: true, isWorking: false, maxRows: 20, bodyColumns: 100 }
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'terminal', component: 'AbovePrompt', props } as never)
    expect(await ui.find({ type: 'Text', text: 'Workstream Name' })).toBeDefined()
    await ui.unmount()
  })
})
