import { describe, expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { OWNER, own } from './own.ts'

import { modelLabel } from '../hooks/prompt-band.tsx'
import { cellsRead, file, pngRead } from './png'

type State = 'upcoming' | 'active' | 'complete'
const IDS = ['basics', 'harness', 'models', 'timing', 'write-validate'] as const
const TITLES = ['Basics', 'Harness', 'Models', 'Timing', 'Write / Validate']
const CHECKLIST = ['Settle the Scope', 'Write the Plan & Config', 'Propose Sizes', 'Scaffold the Workstream', 'Validate']

const ANSWERS = {
  basics: { workstream: 'New Workstream Name', targetBranch: 'staging', integration: 'pr-merge', tickets: false, scopeFrom: 'interview' },
  harness: {
    detected: ['claude', 'codex', 'pi'],
    harnesses: [{ name: 'claude', tier: 'standard' }, { name: 'codex', tier: 'light' }],
    mainOrchestratorHarness: 'claude',
  },
  models: {
    modelSet: 'opinionated',
    models: {
      claude: {
        mainOrchestrator: { model: 'claude-opus-5-5', effort: 'high' },
        orchestrationWorker: { model: 'claude-sonnet-5-5', effort: 'medium' },
        subagent: { model: 'claude-sonnet-5-5', effort: 'low' },
        subagentSimple: 'claude-haiku-5-5',
      },
    },
    maxConcurrency: 16,
  },
  timing: { mode: 'later', localTime: '2026-10-21 02:00', timezone: 'America/Chicago', utcTime: '2026-10-21T07:00:00Z' },
  'write-validate': {},
}

// The band as set_prompt_band.py writes it with `step` active and every step before it complete.
const band = (step: (typeof IDS)[number], extra: { ended?: boolean; ticks?: number; stepDone?: boolean } = {}) => {
  const at = IDS.indexOf(step)
  return {
    step,
    ended: extra.ended ?? false,
    updatedAt: new Date().toISOString(),
    steps: IDS.map((id, i) => ({
      id,
      title: TITLES[i],
      state: (i < at || (i === at && extra.stepDone) ? 'complete' : i === at ? 'active' : 'upcoming') as State,
      answers: i <= at ? ANSWERS[id] : {},
    })),
    checklist: CHECKLIST.map((title, i) => ({ id: `c${i}`, title, done: i < (extra.ticks ?? 0) })),
  }
}

// .orca/prompts/_prompt-band.json holds `file.band`, if any, and ws/_status.json
// `file.status`; avatar SVGs read as one tiny frame. `turns` 0 is a fresh startup.
const world = (on: On, file: { band?: object; status?: object; config?: object }, turns = 1, served: string[] = [], vars: Record<string, string> = {}) => {
  on('fs.list', async () => ({ value: file.status ? [{ name: 'ws', kind: 'dir', size: 0, mtimeMs: 0, isLink: false }] : [] }) as never)
  on('fs.read', async ($, e) => {
    if (e.path.endsWith('.owner')) return { value: OWNER }
    if (file.band && e.path.endsWith('.orca/prompts/_prompt-band.json')) return { value: JSON.stringify(file.band) }
    if (file.status && e.path.endsWith('ws/_status.json')) return { value: JSON.stringify(file.status) }
    if (file.config && e.path.endsWith('.orca/prompts/New Workstream Name/_config.json')) return { value: JSON.stringify(file.config) }
    if (e.path.endsWith('.svg')) served.push(e.path)
    if (e.path.endsWith('.svg')) return { value: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 53" width="48" height="53"><rect x="0" y="0" width="1" height="1" fill="#000"/></svg>' }
    if (e.path.endsWith('.png')) return pngRead(e.path)
    if (e.path.endsWith('.cells')) return cellsRead(e.path)
    throw new Error(`ENOENT ${e.path}`)
  })
  on('session.start', async ($, e) => ({ cwd: e.cwd }))
  on('command.register', async () => ({ value: undefined }) as never)
  on('env.get', async ($, e) => ({ value: vars[e.name] }) as never)
  on('session.turns', async () => ({ value: turns }) as never)
  on('session.end', async ($, e) => ({ sessionId: e.sessionId }) as never)
  on('config.list', async () => ({ value: [] }) as never)
  on('ui.render', { component: 'AbovePrompt' }, ($, e) => h($.ui.resolve(e).Text, {}, 'engine band') as never)
  // The engine's own question node, which a tree around the dialog holds once.
  on('ui.render', { component: 'AskUserQuestion' }, () => ({ type: 'engine', ref: 0 }) as never)
  return mock.clock(on)
}
const start = { cwd: '/repo', surface: 'terminal', isInteractive: true } as const
const mount = ($: any, surface: 'terminal' | 'desktop' = 'terminal', hasSurvey = false) =>
  $.ui.mount({
    plugin: 'orca-helpers',
    surface,
    component: 'AbovePrompt',
    props: { hasSurvey, isWorking: false, maxRows: 30, bodyColumns: 120 },
  } as never)

const QUESTION = { tool: 'AskUserQuestion', questions: [{ question: 'Which model?', header: 'Worker', multiSelect: false, options: [{ label: 'a', description: 'a' }, { label: 'b', description: 'b' }] }] }
const ask = ($: any, surface: 'terminal' | 'desktop' = 'terminal') =>
  $.ui.mount({ plugin: 'orca-helpers', surface, component: 'AskUserQuestion', props: QUESTION } as never)

// A Workstream's _config.json, as scaffold.py reads it: Work Items route to the nearest tier.
const CONFIG = {
  workstream: 'New Workstream Name',
  targetBranch: 'staging',
  integration: 'pr-merge',
  harnesses: [{ name: 'claude', tier: 'standard' }, { name: 'pi', tier: 'light' }],
  workItems: [
    { id: '01-a', size: 'light', wave: 1 },
    { id: '02-b', size: 'standard', wave: 1 },
    { id: '03-c', size: 'standard', wave: 2 },
  ],
}

const STATUS = { workstream: 'Wave Workstream', active: true, items: [{ id: 'a', title: 'Docs', wave: 1, state: 'todo', reason: null }] }

describe('prompt band', () => {
  test('modelLabel shortens a Model Slot and its effort', () => {
    expect(modelLabel({ model: 'claude-opus-5-5', effort: 'high' })).toBe('Opus 5.5 (H)')
    expect(modelLabel({ model: 'gpt-6.1-sol', effort: 'xhigh' })).toBe('GPT 6.1 Sol (XH)')
    expect(modelLabel('claude-haiku-5-5')).toBe('Haiku 5.5')
    expect(modelLabel(null)).toBe('—')
  })

  test('terminal: draws the top bar and the Basics panel', async ($, on) => {
    own(on)
    world(on, { band: band('basics') })
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    expect((await ui.find({ type: 'Text', text: 'Basics' }))!.props.color).toBe('blue')
    expect((await ui.find({ type: 'Text', text: 'Harness' }))!.props.color).toBe('gray')
    expect(await ui.find({ type: 'Text', text: 'New Workstream Name' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'PR + merge' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Interview Me Now' })).toBeDefined()
    expect(await file(ui, 'icon-orca')).toMatch(/\/hooks\/assets\/orca_\d\.png$/)
    expect(await file(ui, 'icon-basics')).toMatch(/\/hooks\/assets\/wave_\d\.png$/)
    expect(await file(ui, 'icon-harness')).toMatch(/\/hooks\/assets\/upcoming_0\.png$/)
    expect(await file(ui, 'icon-write-validate')).toMatch(/\/hooks\/assets\/flag_0\.png$/)
    await ui.unmount()
  })

  test('holds a finished step for 3 seconds, then shows the next', async ($, on) => {
    const state: { band?: object } = { band: band('basics', { stepDone: true }) }
    own(on)
    const clock = world(on, state)
    await $.session.start(start)
    const ui = await mount($)
    state.band = band('harness')
    await clock.advance(2000)
    expect(await file(ui, 'icon-basics')).toMatch(/check_0\.png$/)
    expect(await ui.find({ type: 'Text', text: 'Codex' })).toBeUndefined()
    await clock.advance(3000)
    expect(await ui.find({ type: 'Text', text: 'Codex' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'New Workstream Name' })).toBeDefined()
    await ui.unmount()
  })

  test('a finished step Button shows the answers up to it again', async ($, on) => {
    own(on)
    world(on, { band: band('models') })
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: 'New Workstream Name' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Orchestrator Opus 5.5 (H)' })).toBeDefined()
    await ui.press({ key: 'step-basics' })
    expect(await ui.find({ type: 'Text', text: 'New Workstream Name' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Orchestrator Opus 5.5 (H)' })).toBeUndefined()
    await ui.press({ key: 'step-basics' })
    expect(await ui.find({ type: 'Text', text: 'Orchestrator Opus 5.5 (H)' })).toBeDefined()
    await ui.unmount()
  })

  test('a band file write with the same step clears the pin', async ($, on) => {
    const state: { band?: object } = { band: band('models') }
    own(on)
    const clock = world(on, state)
    await $.session.start(start)
    const ui = await mount($)
    await ui.press({ key: 'step-basics' })
    expect(await ui.find({ type: 'Text', text: 'Orchestrator Opus 5.5 (H)' })).toBeUndefined()
    state.band = band('models', { ticks: 1 })
    await clock.advance(2000)
    expect(await ui.find({ type: 'Text', text: 'Orchestrator Opus 5.5 (H)' })).toBeDefined()
    await ui.unmount()
  })

  test('Harness: crowned Main, dancing selected, disabled unselected', async ($, on) => {
    own(on)
    world(on, { band: band('harness') })
    await $.session.start(start)
    const ui = await mount($)
    expect(await file(ui, 'avatar-claude')).toMatch(/\/avatars\/claude_main_\d\.png$/)
    expect(await file(ui, 'avatar-codex')).toMatch(/\/avatars\/codex_selected_\d\.png$/)
    expect(await file(ui, 'avatar-pi')).toMatch(/\/avatars\/pi_disabled_0\.png$/)
    // 5 rows: the export crops the art's blank headroom, so no empty row sits above the Avatars.
    expect((await ui.find({ type: 'Image', key: 'avatar-claude' }))!.props.rows).toBe(5)
    expect(await ui.find({ type: 'Text', text: 'Main' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Codex' })).toBeDefined()
    expect((await ui.find({ type: 'Text', text: 'Pi' }))!.props.dimColor).toBe(true)
    await ui.unmount()
  })

  test('Models: one untruncated line per Model Slot at 160 body columns', async ($, on) => {
    own(on)
    world(on, { band: band('models') })
    await $.session.start(start)
    const ui = await $.ui.mount({
      plugin: 'orca-helpers',
      surface: 'terminal',
      component: 'AbovePrompt',
      props: { hasSurvey: false, isWorking: false, maxRows: 30, bodyColumns: 160 },
    } as never)
    // mainOrchestrator, orchestrationWorker, subagent, subagentSimple, each its own Text.
    for (const text of ['Orchestrator Opus 5.5 (H)', 'Worker Sonnet 5.5 (M)', 'Subagent Sonnet 5.5 (L)', 'Simple Haiku 5.5']) {
      const line = await ui.find({ type: 'Text', text })
      expect(line).toBeDefined()
      // No truncate wrap, so the engine draws no `…`.
      expect(line!.props.wrap).toBeUndefined()
    }
    await ui.unmount()
  })

  test('Models: the workers table with efforts and the concurrency', async ($, on) => {
    own(on)
    world(on, { band: band('models') })
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: '16' })).toBeDefined()
    // Every answer so far stays in view.
    expect(await ui.find({ type: 'Text', text: 'PR + merge' })).toBeDefined()
    await ui.unmount()
  })

  test('Timing: Schedule for later shows the Waiting avatar and the time', async ($, on) => {
    own(on)
    world(on, { band: band('timing') })
    await $.session.start(start)
    const ui = await mount($)
    expect(await file(ui, 'avatar-claude')).toMatch(/claude_waiting_\d\.png$/)
    expect(await ui.find({ type: 'Text', text: '2026-10-21 02:00 America/Chicago' })).toBeDefined()
    await ui.unmount()
  })

  test('Write / Validate: ticks the checklist and stops the flag at the end', async ($, on) => {
    const state: { band?: object } = { band: band('write-validate', { ticks: 2 }) }
    own(on)
    const clock = world(on, state)
    await $.session.start(start)
    const ui = await mount($)
    expect(await file(ui, 'avatar-claude')).toMatch(/claude_writing_\d\.png$/)
    expect((await ui.find({ type: 'Text', text: '✔ Write the Plan & Config' }))!.props.color).toBe('green')
    expect((await ui.find({ type: 'Text', text: '○ Propose Sizes' }))!.props.color).toBe('gray')
    const flag = await file(ui, 'icon-write-validate')
    await clock.advance(200)
    expect(await file(ui, 'icon-write-validate')).not.toBe(flag)

    state.band = band('write-validate', { ticks: 5, stepDone: true, ended: true })
    await clock.advance(2000)
    expect(await file(ui, 'icon-write-validate')).toMatch(/flag_0\.png$/)
    await clock.advance(400)
    expect(await file(ui, 'icon-write-validate')).toMatch(/flag_0\.png$/)
    expect((await ui.find({ type: 'Text', text: 'Write / Validate' }))!.props.color).toBe('gray')
    // The finished band stays up: nothing but a startup or /clear hides it.
    await clock.advance(62_000)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'engine band' })).toBeUndefined()
    await ui.unmount()
  })

  test('desktop: draws icons and avatars as SVG, one frame per file', async ($, on) => {
    own(on)
    world(on, { band: band('harness') })
    await $.session.start(start)
    const ui = await mount($, 'desktop')
    const svgs = await ui.findAll({ type: 'Svg' })
    expect(svgs.map(s => s.props.alt)).toContain('Claude Code')
    const claude = svgs.find(s => s.props.alt === 'Claude Code')!
    expect(claude.props.source).toMatch(/viewBox="0 0 48 53" width="48"/)
    expect(claude.props.height).toBe(53)
    await ui.unmount()
  })

  test('desktop: Pi shows selected from one frame file, under the Svg source cap', async ($, on) => {
    const b = band('harness')
    b.steps[1]!.answers = { ...ANSWERS.harness, detected: ['claude', 'pi'], harnesses: [{ name: 'claude', tier: 'standard' }, { name: 'pi', tier: 'standard' }] }
    const served: string[] = []
    own(on)
    world(on, { band: b }, 1, served)
    await $.session.start(start)
    const ui = await mount($, 'desktop')
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    expect(served.some(p => /\/pi_selected_\d+\.svg$/.test(p))).toBe(true)
    for (const p of served) expect(p).toMatch(/\/avatars\/\w+_\w+_\d+\.svg$/)
    const avatars = (await ui.findAll({ type: 'Svg' })).filter(s => ['Claude Code', 'Pi'].includes(s.props.alt as string))
    expect(avatars.map(s => s.props.alt)).toEqual(expect.arrayContaining(['Claude Code', 'Pi']))
    for (const s of avatars) expect((s.props.source as string).length).toBeLessThanOrEqual(131072)
    await ui.unmount()
  })

  test('startup hides the band it finds; the next write shows it', async ($, on) => {
    const state: { band?: object } = { band: band('write-validate', { ended: true, stepDone: true }) }
    own(on)
    const clock = world(on, state, 0)
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: 'engine band' })).toBeDefined()
    state.band = band('basics')
    await clock.advance(2000)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    await ui.unmount()
  })

  test('leaves the band to others with no band file', async ($, on) => {
    own(on)
    world(on, {})
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: 'engine band' })).toBeDefined()
    await ui.unmount()
  })

  test('resume keeps an ended band up', async ($, on) => {
    own(on)
    world(on, { band: band('write-validate', { ended: true, stepDone: true }) }, 3)
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    await ui.unmount()
  })

  test('/clear hides the band; the next write shows it', async ($, on) => {
    const state: { band?: object } = { band: band('write-validate', { ended: true, stepDone: true }) }
    own(on)
    const clock = world(on, state, 3)
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    await $.session.end({ reason: 'clear', sessionId: 's1', resume: {} } as never)
    expect(await ui.find({ type: 'Text', text: 'engine band' })).toBeDefined()
    state.band = band('basics')
    await clock.advance(2000)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    await ui.unmount()
  })

  test('stays up while a question shows', async ($, on) => {
    own(on)
    world(on, { band: band('basics') })
    await $.session.start(start)
    const ui = await mount($, 'terminal', true)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    await ui.unmount()
  })

  test('a live interview takes the place of an active Workstream', async ($, on) => {
    own(on)
    world(on, { band: band('harness'), status: STATUS })
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Wave Workstream' })).toBeUndefined()
    await ui.unmount()
  })

  test('an interview untouched for 30 minutes gives the place back to the Wave Band', async ($, on) => {
    own(on)
    world(on, { band: { ...band('harness'), updatedAt: new Date(Date.now() - 31 * 60 * 1000).toISOString() }, status: STATUS })
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: 'Wave Workstream' })).toBeDefined()
    await ui.unmount()
  })

  test('`end` hands the place back to the Wave Band', async ($, on) => {
    const state: { band?: object; status?: object } = { band: band('write-validate', { ticks: 4 }), status: STATUS }
    own(on)
    const clock = world(on, state)
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    state.band = band('write-validate', { ended: true, stepDone: true, ticks: 5 })
    await clock.advance(2000)
    expect(await ui.find({ type: 'Text', text: 'Wave Workstream' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeUndefined()
    await ui.unmount()
  })

  // Orca reads no kitty image file outside the workspace and the temp folders,
  // and the plugin root is in neither: a `file` source draws an empty box there.
  test('terminal: both bands send their pictures as PNG bytes, never a file name', async ($, on) => {
    const state: { band?: object; status?: object } = { band: band('harness') }
    own(on)
    const clock = world(on, state)
    await $.session.start(start)
    const ui = await mount($)
    const images = async () => (await ui.findAll({ type: 'Image' })).map((i: any) => i.props.source)
    const prompt = await images()
    expect(prompt.length).toBeGreaterThan(0)
    for (const source of prompt) expect(Object.keys(source)).toEqual(['png'])

    state.band = band('write-validate', { ended: true, stepDone: true })
    state.status = STATUS
    await clock.advance(2000)
    expect(await ui.find({ type: 'Text', text: 'Wave Workstream' })).toBeDefined()
    const wave = await images()
    expect(wave.length).toBeGreaterThan(0)
    for (const source of wave) expect(Object.keys(source)).toEqual(['png'])
    expect(await file(ui, 'avatar-a')).toMatch(/\/avatars\/claude_todo_[a-z]+_24_\d\.png$/)
    await ui.unmount()
  })

  test('the caret collapses the panel, and the Wave Band reads the same toggle', async ($, on) => {
    const state: { band?: object; status?: object } = { band: band('basics') }
    own(on)
    const clock = world(on, state)
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: 'New Workstream Name' })).toBeDefined()
    await ui.press({ key: 'caret' })
    expect(await ui.find({ type: 'Text', text: 'New Workstream Name' })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()

    // The Prompt Band goes and a Workstream starts: the Wave Band comes up collapsed.
    delete state.band
    state.status = STATUS
    await clock.advance(2000)
    expect(await ui.find({ type: 'Text', text: 'Wave Workstream' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'TO DO' })).toBeUndefined()
    await ui.press({ key: 'caret' })
    expect(await ui.find({ type: 'Text', text: 'TO DO' })).toBeDefined()

    delete state.status
    state.band = band('basics')
    await clock.advance(2000)
    expect(await ui.find({ type: 'Text', text: 'New Workstream Name' })).toBeDefined()
    await ui.unmount()
  })

  test('stepper: the steps run down the left beside a 4×2 orca, the shown one marked', async ($, on) => {
    own(on)
    world(on, { band: band('models') })
    await $.session.start(start)
    const ui = await mount($)
    const orca = (await ui.find({ type: 'Image', key: 'icon-orca' }))!
    expect([orca.props.columns, orca.props.rows]).toEqual([4, 2])
    expect((await ui.find({ type: 'Box', key: 'row-models' }))!.props.backgroundColor).toBeDefined()
    expect((await ui.find({ type: 'Box', key: 'row-basics' }))!.props.backgroundColor).toBeUndefined()
    expect((await ui.find({ type: 'Text', text: 'Timing' }))!.props.dimColor).toBe(true)
    await ui.unmount()
  })

  test('desktop: the orca draws at 32 px', async ($, on) => {
    own(on)
    world(on, { band: band('basics') })
    await $.session.start(start)
    const ui = await mount($, 'desktop')
    const orca = (await ui.findAll({ type: 'Svg' })).find(s => s.props.alt === '◖◗')!
    expect([orca.props.width, orca.props.height]).toEqual([32, 32])
    await ui.unmount()
  })

  // TERM_PROGRAM=Orca without CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1: pictures are off (hooks/images.ts).
  for (const off of [true, false]) {
    test(`terminal, pictures ${off ? 'off' : 'on'}: step icons, Harness Avatars and the H1 orca draw as ${off ? 'Rasters' : 'Images'}`, async ($, on) => {
      own(on)
      world(on, { band: band('harness') }, 1, [], off ? { TERM_PROGRAM: 'Orca' } : {})
      await $.session.start(start)
      const ui = await mount($)
      const strip = await ask($)
      const sizes = { 'icon-orca': [4, 2], 'icon-basics': [2, 1], 'icon-harness': [2, 1], 'icon-write-validate': [2, 1], 'avatar-claude': [9, 5], 'avatar-codex': [9, 5], 'avatar-pi': [9, 5] }
      const drawn = [...Object.entries(sizes).map(([key, size]) => [ui, key, size] as const), [strip, 'strip-orca', [2, 1]] as const]
      for (const [mounted, key, size] of drawn) {
        const raster = await mounted.find({ type: 'Raster', key })
        const image = await mounted.find({ type: 'Image', key })
        expect(raster === undefined).toBe(!off)
        expect(image === undefined).toBe(off)
        expect([(raster ?? image)!.props.columns, (raster ?? image)!.props.rows]).toEqual(size)
      }
      if (off) {
        expect([...(await ui.findAll({ type: 'Image' })), ...(await strip.findAll({ type: 'Image' }))]).toEqual([])
        for (const alt of ['◖◗', '✔ ', '▂▄', '━━', '▚▞']) expect(await ui.find({ type: 'Text', text: alt })).toBeUndefined()
        expect(await strip.find({ type: 'Text', text: '◖◗' })).toBeUndefined()
      }
      await Promise.all([ui.unmount(), strip.unmount()])
    })
  }

  test('H1: a live interview draws one strip above the question', async ($, on) => {
    own(on)
    world(on, { band: band('models') })
    await $.session.start(start)
    const ui = await ask($)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    expect(await ui.find({ type: 'engine' })).toBeDefined()
    expect((await ui.findAll({ type: 'Text', text: '▶ Models ' })).map(t => t.props.color)).toContain('blue')
    expect(await ui.find({ type: 'Text', text: '✔ Basics ' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: '· Timing ' })).toBeDefined()
    await ui.unmount()
  })

  test('H1: no strip outside a live interview', async ($, on) => {
    const state: { band?: object } = {}
    own(on)
    const clock = world(on, state)
    await $.session.start(start)
    const ui = await ask($)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeUndefined()
    state.band = band('write-validate', { ended: true, stepDone: true })
    await clock.advance(2000)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeUndefined()
    expect(await ui.find({ type: 'engine' })).toBeDefined()
    await ui.unmount()
  })

  test('H1: a strip past the 12-row limit leaves the question unchanged', async ($, on) => {
    const b = band('models')
    b.steps[0]!.title = 'x'.repeat(12 * 40)
    own(on)
    world(on, { band: b })
    await $.session.start(start)
    const ui = await ask($)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeUndefined()
    expect(await ui.find({ type: 'engine' })).toBeDefined()
    await ui.unmount()
  })

  test('Ready: opens by itself at `end` with the Waves, the route and the next command', async ($, on) => {
    const state: { band?: object; config?: object } = { band: band('write-validate', { ticks: 4 }), config: CONFIG }
    own(on)
    const clock = world(on, state)
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: 'Ready' })).toBeUndefined()
    state.band = band('write-validate', { ended: true, stepDone: true, ticks: 5 })
    await clock.advance(2000)
    expect(await ui.find({ type: 'Text', text: 'Ready' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: '2 Work Items · Pi, Claude Code' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: '1 Work Item · Claude Code' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'PR + merge into staging' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Scheduled 2026-10-21 02:00 America/Chicago' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Next: nothing to run, it starts at 2026-10-21 02:00 America/Chicago' })).toBeDefined()
    // An earlier tab still opens, and Ready opens again.
    await ui.press({ key: 'step-basics' })
    expect(await ui.find({ type: 'Text', text: 'PR + merge into staging' })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: 'New Workstream Name' })).toBeDefined()
    await ui.press({ key: 'step-ready' })
    expect(await ui.find({ type: 'Text', text: 'PR + merge into staging' })).toBeDefined()
    await ui.unmount()
  })

  test('Ready: a run-now Workstream names /orca-execute', async ($, on) => {
    const b = band('write-validate', { ended: true, stepDone: true })
    b.steps[3]!.answers = { mode: 'now' }
    own(on)
    world(on, { band: b, config: CONFIG })
    await $.session.start(start)
    const ui = await mount($)
    expect(await ui.find({ type: 'Text', text: 'Next: run /orca-execute New Workstream Name' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Now' })).toBeDefined()
    await ui.unmount()
  })
})
