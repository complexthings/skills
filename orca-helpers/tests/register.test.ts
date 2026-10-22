import { describe, expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { OWNER, own } from './own.ts'

const SETTINGS = '.orca/prompts/prompt-settings.json'
const PRIORITY = {
  modelOrder: {
    anthropic: {
      orchestrationWorker: [{ model: 'claude-opus-5-5', effort: 'medium' }],
      subagent: [{ model: 'claude-opus-5-5', effort: 'low' }],
      subagentSimple: [{ model: 'claude-haiku-5-5', effort: null }],
    },
  },
}
const settings = (models: Record<string, { model: string }>, harness = 'claude') => ({
  harnesses: [{ name: harness, cli: harness, tier: 'standard', models }],
  priorityFile: 'data/priority.json',
})

// Answers $.fs beneath the plugin from these files, and records $.ui.log.
const world = (on: On, files: Record<string, unknown>) => {
  const logged: string[] = []
  const reads: string[] = []
  on('fs.read', async ($, e) => {
    if (e.path.endsWith('.owner')) return { value: OWNER }
    // $.fs resolves a relative path against the working directory.
    const name = Object.keys(files).find(name => e.path.endsWith(`/${name}`))
    if (name === undefined) throw new Error(`ENOENT ${e.path}`)
    reads.push(name)
    return { value: JSON.stringify(files[name]) }
  })
  on('ui.log', async ($, e) => { logged.push(e.text); return { value: undefined } })
  on('session.start', async ($, e) => ({ cwd: e.cwd }))
  on('command.register', async () => ({ value: undefined }) as never)
  on('env.get', async () => ({ value: undefined }) as never)
  on('session.turns', async () => ({ value: 0 }) as never)
  on('session.id', async () => ({ value: OWNER }) as never)
  return Object.assign(logged, { reads })
}
const start = { cwd: '/repo', surface: 'terminal', isInteractive: true } as const

describe('status guard', () => {
  for (const tool of ['Edit', 'Write'] as const) {
    test(`${tool} on a _status.json under .orca/prompts is denied`, async ($, on) => {
      on('tool.call', async () => ({ result: 'wrote' }) as never)
      const ran = await $.tool.call({
        tool, tool_use_id: 't1', file_path: '/repo/.orca/prompts/ws/_status.json',
        content: '{}', old_string: 'a', new_string: 'b',
      } as never)
      expect(ran.deny).toContain('set_status.py')
    })
  }

  for (const tool of ['Edit', 'Write'] as const) {
    test(`${tool} on .orca/prompts/_prompt-band.json is denied`, async ($, on) => {
      on('tool.call', async () => ({ result: 'wrote' }) as never)
      const ran = await $.tool.call({
        tool, tool_use_id: 't3', file_path: '/repo/.orca/prompts/_prompt-band.json',
        content: '{}', old_string: 'a', new_string: 'b',
      } as never)
      expect(ran.deny).toContain('set_prompt_band.py')
    })
  }

  test('other files pass through', async ($, on) => {
    on('tool.call', async () => ({ result: 'wrote' }) as never)
    for (const file_path of ['/repo/.orca/prompts/ws/_config.json', '/repo/notes/_status.json', '/repo/notes/_prompt-band.json']) {
      const ran = await $.tool.call({
        tool: 'Write', tool_use_id: 't2', file_path, content: '{}',
      } as never)
      expect(ran.deny).toBeUndefined()
    }
  })
})

describe('stale settings warning', () => {
  test('warns once, naming the model the Priority File lacks', async ($, on) => {
    const logged = world(on, {
      [SETTINGS]: settings({ mainOrchestrator: { model: 'claude-opus-5-5' }, subagent: { model: 'claude-opus-4-1' } }),
      'data/priority.json': PRIORITY,
    })
    await $.session.start(start)
    expect(logged.length).toBe(1)
    expect(logged[0]).toContain('claude.subagent: claude-opus-4-1')
    expect(logged[0]).not.toContain('mainOrchestrator')
  })

  test('stays quiet when every model is ranked', async ($, on) => {
    const logged = world(on, {
      [SETTINGS]: settings({ orchestrationWorker: { model: 'claude-opus-5-5' }, subagentSimple: { model: 'claude-haiku-5-5' } }),
      'data/priority.json': PRIORITY,
    })
    await $.session.start(start)
    expect(logged).toEqual([])
    expect(logged.reads).toEqual([SETTINGS, 'data/priority.json'])
  })

  test('reads plain-string slots and treats . and - as one', async ($, on) => {
    const logged = world(on, {
      [SETTINGS]: { ...settings({}), harnesses: [{ name: 'claude', models: { subagent: 'claude-opus-5.5', subagentSimple: 'claude-haiku-4-1' } }] },
      'data/priority.json': PRIORITY,
    })
    await $.session.start(start)
    expect(logged[0]).toContain('claude.subagentSimple: claude-haiku-4-1')
    expect(logged[0]).not.toContain('subagent:')
  })

  test('skips discovered harnesses and repos without settings', async ($, on) => {
    const logged = world(on, {
      [SETTINGS]: settings({ subagent: { model: 'anything' } }, 'pi'),
      'data/priority.json': PRIORITY,
    })
    await $.session.start(start)
    expect(logged).toEqual([])
  })

  test('stays quiet with no settings file', async ($, on) => {
    const logged = world(on, {})
    await $.session.start(start)
    expect(logged).toEqual([])
  })
})

// A Desktop session can load the module after session.start has fired, so
// the first band draw has to start the polls itself.
describe('bands without session.start', () => {
  const BAND = { component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 30, bodyColumns: 120 } } as never
  const STATUS = { workstream: 'Workstream Name', active: true, items: [{ id: 'a', title: 'Docs', wave: 1, state: 'todo', reason: null }] }
  const PROMPT_BAND = {
    step: 'basics', ended: false, updatedAt: new Date().toISOString(),
    steps: [{ id: 'basics', title: 'Basics', state: 'active', answers: {} }],
    checklist: [],
  }
  const bands = (on: On, files: Record<string, unknown>) => {
    on('fs.list', async () => ({ value: [{ name: 'ws', kind: 'dir', size: 0, mtimeMs: 0, isLink: false }] }) as never)
    on('fs.read', async ($, e) => {
      if (e.path.endsWith('.owner')) return { value: OWNER }
      const name = Object.keys(files).find(name => e.path.endsWith(name))
      if (name === undefined) throw new Error(`ENOENT ${e.path}`)
      return { value: JSON.stringify(files[name]) }
    })
    on('config.list', async () => ({ value: [] }) as never)
    on('ui.render', { component: 'AbovePrompt' }, ($, e) => h($.ui.resolve(e).Text, {}, 'engine band') as never)
  }

  test('desktop: the Wave band draws on its first render', async ($, on) => {
    own(on)
    bands(on, { 'ws/_status.json': STATUS })
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'desktop', ...(BAND as object) } as never)
    expect(await ui.find({ type: 'Text', text: 'Workstream Name' })).toBeDefined()
    await ui.unmount()
  })

  test('desktop: the Prompt Band draws on its first render', async ($, on) => {
    own(on)
    bands(on, { '_prompt-band.json': PROMPT_BAND })
    const ui = await $.ui.mount({ plugin: 'orca-helpers', surface: 'desktop', ...(BAND as object) } as never)
    expect(await ui.find({ type: 'Text', text: 'Orca Prompt' })).toBeDefined()
    await ui.unmount()
  })
})
