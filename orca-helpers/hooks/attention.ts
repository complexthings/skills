// Attention capture (ADR 0014): the question tool in the Owning Session, while a
// Workstream is active, opens an Attention Item in its _status.json through
// set_status.py --attention, and its result clears it. Any other session writes nothing.
import type { EngineInterface as Dollar, Register } from 'claude-code'

import { activeStatus } from './band.tsx'
import { isWaveOwner } from './owner.ts'

const setStatus = ($: Dollar, dir: string, args: string[]) =>
  $.process.run(['python3', `${$.plugin.root}/skills/orca-prompt/scripts/set_status.py`, dir, '--attention', ...args]).catch(() => undefined)

export function registerAttention(on: Parameters<Register>[0]) {
  on('tool.call', { tool: 'AskUserQuestion' }, async ($, e, next) => {
    const { found, path } = await activeStatus($)
    const owned = found !== undefined && (await isWaveOwner($, path))
    if (!owned) return next(e)
    const dir = path.replace(/\/_status\.json$/, '')
    // shortcut: a call with several questions records the first with a count of the rest; list them all if the Board needs it.
    const [first, ...more] = e.questions
    if (first) await setStatus($, dir, ['question', more.length ? `${first.question} (+${more.length} more)` : first.question, ...first.options.map(o => o.label)])
    try {
      return await next(e)
    } finally {
      await setStatus($, dir, ['--clear'])
    }
  })
}
