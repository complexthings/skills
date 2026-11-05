import { describe, expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { COMMENT, LINE } from '../hooks/images.ts'
import { own } from './own.ts'

// The environment as `vars`, the home directory as `files`, and every write recorded.
const world = (on: On, vars: Record<string, string>, files: Record<string, string> = {}) => {
  const writes: string[] = []
  on('env.get', async ($, e) => ({ value: vars[e.name] }))
  on('fs.read', async ($, e) => {
    if (e.path in files) return { value: files[e.path] }
    throw new Error(`ENOENT ${e.path}`)
  })
  on('fs.write', async ($, e) => { files[e.path] = e.text; writes.push(e.path); return { value: undefined } })
  on('session.start', async ($, e) => ({ cwd: e.cwd }))
  on('command.register', async () => ({ value: undefined }) as never)
  on('session.turns', async () => ({ value: 1 }) as never)
  on('fs.list', async () => ({ value: [] }) as never)
  on('config.list', async () => ({ value: [] }) as never)
  return { files, writes }
}
const start = { cwd: '/repo', surface: 'terminal', isInteractive: true } as const
const OFF = { TERM_PROGRAM: 'Orca', HOME: '/home/u' }

describe('pictures-off toast', () => {
  test('shows once with pictures off, in a session that owns nothing', async ($, on) => {
    const env = own(on)
    env.session = 'session-b'
    world(on, OFF)
    await $.session.start(start)
    await $.session.start(start)
    expect(env.toasts.filter(t => t.includes('/orca-images')).length).toBe(1)
  })

  for (const vars of [{ ...OFF, CLAUDE_CODE_FORCE_TERMINAL_IMAGES: '1' }, { TERM_PROGRAM: 'iTerm.app' }]) {
    test(`never shows with ${JSON.stringify(vars)}`, async ($, on) => {
      const env = own(on)
      world(on, vars)
      await $.session.start(start)
      expect(env.toasts.filter(t => t.includes('/orca-images'))).toEqual([])
    })
  }
})

describe('/orca-images', () => {
  test('writes the line once to ~/.zshrc, and a second run changes nothing', async ($, on) => {
    const { files, writes } = world(on, { ...OFF, SHELL: '/bin/zsh' }, { '/home/u/.zshrc': 'export A=1' })
    await $.session.start(start)
    const first = await $.command.run({ command: 'orca-images' })
    expect(files['/home/u/.zshrc']).toBe(`export A=1\n\n${COMMENT}\n${LINE}\n`)
    expect(first.text).toContain('/home/u/.zshrc')
    expect(first.text).toContain('Restart Claude')
    const second = await $.command.run({ command: 'orca-images' })
    expect(writes).toEqual(['/home/u/.zshrc'])
    expect(second.text).toContain('already has the line')
  })

  test('creates ~/.bashrc for bash', async ($, on) => {
    const { files } = world(on, { ...OFF, SHELL: '/usr/local/bin/bash' })
    await $.session.start(start)
    await $.command.run({ command: 'orca-images' })
    expect(files['/home/u/.bashrc']).toBe(`\n${COMMENT}\n${LINE}\n`)
  })

  test('an unknown shell gets the line without a write', async ($, on) => {
    const { writes } = world(on, { ...OFF, SHELL: '/usr/bin/fish' })
    await $.session.start(start)
    const ran = await $.command.run({ command: 'orca-images' })
    expect(ran.text).toContain(LINE)
    expect(writes).toEqual([])
  })
})
