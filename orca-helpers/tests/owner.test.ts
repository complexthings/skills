import { describe, expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { claimOf, isPromptOwner, isWaveOwner } from '../hooks/owner.ts'

const BEGIN = 'python3 /p/skills/orca-prompt/scripts/set_prompt_band.py .orca/prompts begin'
const START = 'python3 /p/skills/orca-prompt/scripts/set_status.py .orca/prompts/ws --start'

// An in-memory $.fs, a switchable session id, and a Bash that fails when `fail` says so.
const world = (on: On) => {
  // The files the scripts write; the hook writes a .owner only beside one of these.
  const files: Record<string, string> = { '.orca/prompts/_prompt-band.json': '{}', '.orca/prompts/ws/_status.json': '{}' }
  const env = { session: 'session-a', fail: false }
  on('fs.read', async ($, e) => {
    const name = Object.keys(files).find(name => e.path.endsWith(name))
    if (name === undefined) throw new Error(`ENOENT ${e.path}`)
    return { value: files[name] }
  })
  on('fs.write', async ($, e) => {
    files[e.path.replace(/^.*?(\.orca\/)/, '$1')] = e.text
    return { value: undefined }
  })
  on('session.id', async () => ({ value: env.session }) as never)
  on('tool.call', async () =>
    (env.fail
      ? { isError: true, result: 'Exit code 1', text: 'FAIL: bad input' }
      : { result: { stdout: '', stderr: '', interrupted: false } }) as never,
  )
  return Object.assign(env, { files })
}
const bash = (command: string) => ({ tool: 'Bash', tool_use_id: 't1', command }) as never

// The test's own $ is the engine's, with no $.state or $.fs of a plugin's, so the
// checks run on a $ that reads the values the plugin wrote: its state.set calls,
// caught on their way to the kit's store, and the files its fs.write calls left.
const owns = (env: ReturnType<typeof world>, state: Record<string, unknown>, found?: string) => {
  const plugin = {
    state: { get: async (ref: { key: string }) => ({ value: state[ref.key], version: 1 }) },
    fs: { read: async (path: string) => env.files[path] ?? Promise.reject(new Error(`ENOENT ${path}`)) },
    session: { id: async () => env.session },
  } as never
  return Promise.all([isPromptOwner(plugin), isWaveOwner(plugin, found)]).then(([prompt, wave]) => ({ prompt, wave }))
}
const stateOf = (on: On) => {
  const state: Record<string, unknown> = {}
  on('state.set', async ($, e: any, next) => { state[e.key] = e.value; return next(e) })
  return state
}

describe('Owning Session', () => {
  test('a successful begin claims the Prompt Band, a --start the Wave Band', async ($, on) => {
    const state = stateOf(on)
    const env = world(on)
    expect((await owns(env, state)).prompt).toBe(false)
    await $.tool.call(bash(BEGIN))
    expect((await owns(env, state)).prompt).toBe(true)
    expect((await owns(env, state)).wave).toBe(false)
    await $.tool.call(bash(START))
    expect((await owns(env, state)).wave).toBe(true)
  })

  test('a claim on one _status.json is not ownership of another', async ($, on) => {
    const state = stateOf(on)
    const env = world(on)
    await $.tool.call(bash(START))
    expect((await owns(env, state, '.orca/prompts/ws/_status.json')).wave).toBe(true)
    expect((await owns(env, state, '.orca/prompts/other/_status.json')).wave).toBe(false)
  })

  test('a relative or unnormalised claim still owns its Workstream', async ($, on) => {
    const state = stateOf(on)
    const env = world(on)
    await $.tool.call(bash('python3 /p/skills/orca-prompt/scripts/set_status.py ws --start'))
    env.files['ws/_status.json.owner'] = 'session-a' // the engine absolutises a relative write; the owns read is by claim path
    expect((await owns(env, state, '.orca/prompts/ws/_status.json')).wave).toBe(true)
    expect((await owns(env, state, '.orca/prompts/other/_status.json')).wave).toBe(false)
  })

  test('a claim from inside the Workstream dir still owns it', async ($, on) => {
    const state = stateOf(on)
    const env = world(on)
    await $.tool.call(bash('cd .orca/prompts/ws && python3 /p/skills/orca-prompt/scripts/set_status.py . --start'))
    env.files['./_status.json.owner'] = 'session-a' // as above: the engine absolutises a relative write
    expect((await owns(env, state, '.orca/prompts/ws/_status.json')).wave).toBe(true)
  })

  test('a .owner the script wrote claims, though claimOf cannot read the command', async ($, on) => {
    const state = stateOf(on)
    const env = world(on)
    await $.tool.call(bash('python3 $S $D --start'))
    expect((await owns(env, state, '.orca/prompts/ws/_status.json')).wave).toBe(false)
    env.files['.orca/prompts/ws/_status.json.owner'] = 'session-a\n'
    expect((await owns(env, state, '.orca/prompts/ws/_status.json')).wave).toBe(true)
    env.files['.orca/prompts/ws/_status.json.owner'] = 'session-b'
    expect((await owns(env, state, '.orca/prompts/ws/_status.json')).wave).toBe(false)
  })

  test('a failed call claims nothing', async ($, on) => {
    const state = stateOf(on)
    const env = world(on)
    env.fail = true
    await $.tool.call(bash(BEGIN))
    await $.tool.call(bash(START))
    expect((await owns(env, state)).prompt).toBe(false)
    expect((await owns(env, state)).wave).toBe(false)
    expect(Object.keys(env.files).filter(name => name.endsWith('.owner'))).toEqual([])
  })

  test('a dir the shell expands claims nothing and writes nothing', async ($, on) => {
    const state = stateOf(on)
    const env = world(on)
    for (const dir of ['$D', '"$D"', '${D}', '~/ws', '`pwd`', 'ws*']) {
      expect(claimOf(`python3 x/set_status.py ${dir} --start`)).toBeUndefined()
      expect(claimOf(`python3 x/set_prompt_band.py ${dir} begin`)).toBeUndefined()
      await $.tool.call(bash(`D=.orca/prompts/ws; python3 x/set_status.py ${dir} --start`))
    }
    expect((await owns(env, state)).wave).toBe(false)
    expect(Object.keys(env.files).filter(name => name.endsWith('.owner'))).toEqual([])
  })

  test('a claimed dir with no state file in it gets no .owner', async ($, on) => {
    const env = world(on)
    await $.tool.call(bash('python3 x/set_status.py .orca/prompts/gone --start'))
    expect(Object.keys(env.files).filter(name => name.endsWith('.owner'))).toEqual([])
  })

  test('a later claim in another session clears this one', async ($, on) => {
    const state = stateOf(on)
    const env = world(on)
    await $.tool.call(bash(BEGIN))
    await $.tool.call(bash(START))
    // Session B's claims overwrite the .owner files beside both.
    env.files['.orca/prompts/_prompt-band.json.owner'] = 'session-b'
    env.files['.orca/prompts/ws/_status.json.owner'] = 'session-b'
    expect((await owns(env, state)).prompt).toBe(false)
    expect((await owns(env, state)).wave).toBe(false)
    // Claiming again in this session takes it back: the latest claim wins.
    await $.tool.call(bash(BEGIN))
    expect((await owns(env, state)).prompt).toBe(true)
  })

  test('other commands claim nothing', () => {
    expect(claimOf('python3 set_prompt_band.py .orca/prompts start basics')).toBeUndefined()
    expect(claimOf('python3 set_status.py .orca/prompts/ws a complete')).toBeUndefined()
    expect(claimOf('rtk python set_status.py ".orca/prompts/ws/" --start')).toEqual({ kind: 'wave', path: '.orca/prompts/ws/_status.json' })
  })

  test('a chained command still claims', () => {
    const prompt = { kind: 'prompt', path: '.orca/prompts/_prompt-band.json' }
    const wave = { kind: 'wave', path: '.orca/prompts/ws/_status.json' }
    expect(claimOf(`${BEGIN};`)).toEqual(prompt)
    expect(claimOf(`${BEGIN} && x`)).toEqual(prompt)
    expect(claimOf(`${START};`)).toEqual(wave)
    expect(claimOf(`${START} || x`)).toEqual(wave)
    expect(claimOf(`${START} | tee log`)).toEqual(wave)
    expect(claimOf('python3 set_prompt_band.py .orca/prompts beginning')).toBeUndefined()
  })
})
