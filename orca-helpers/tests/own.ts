// Makes the test session the Owning Session of both bands, and records the
// ambient signals it raises. No `.test.` in the name, so the runner does not collect it.
import type { On } from 'claude-code'

export const OWNER = 'session-a'

// Each test's own fs.read answers a `.owner` read with OWNER.
// `env.session` set to another id makes the test session a non-owner.
// `toasted` stands for what an earlier load of the module saw, as $.state keeps it across a reload.
export const own = (on: On, toasted?: { workstream: string; keys: string[] }) => {
  const env = { session: OWNER, toasts: [] as string[], status: [] as (string | undefined)[] }
  // The claims hooks/owner.ts records after `set_prompt_band.py begin` and `set_status.py --start`.
  const owners = { prompt: '.orca/prompts/_prompt-band.json', wave: '.orca/prompts/ws/_status.json' }
  on('state.get', async ($, e: any, next) => {
    if (e.key === 'owners') return { value: { value: owners, version: 1 } } as never
    if (e.key === 'toasted' && toasted) return { value: { value: toasted, version: 1 } } as never
    return next(e)
  })
  on('session.id', async () => ({ value: env.session }) as never)
  on('ui.toast', async ($, e) => { env.toasts.push(e.text); return { value: undefined } })
  on('ui.status', async ($, e) => { env.status.push(e.text); return { value: undefined } })
  return env
}
