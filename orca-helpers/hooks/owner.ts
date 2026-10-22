// The Owning Session (ADR 0011): the session whose successful
// `set_prompt_band.py begin` or `set_status.py --start` came last.
// $.state holds the file this session claimed; a `<file>.owner` beside it
// holds the claiming session's id, so a later claim in another session
// overwrites it and clears this session's ownership. The scripts write the
// .owner from CLAUDE_CODE_SESSION_ID too, so a claim holds however the command reads.

import { atom, read, update } from 'claude-code'
import type { EngineInterface as Dollar, Register } from 'claude-code'

const owners = atom({ plugin: 'orca-helpers', key: 'owners' } as const, {})

const CLAIMS = [
  { script: 'set_prompt_band.py', flag: 'begin', file: '_prompt-band.json', kind: 'prompt' },
  { script: 'set_status.py', flag: '--start', file: '_status.json', kind: 'wave' },
] as const

/** The file a Bash command claims: `<dir>/<file>` for `<script> <dir> <flag>`. */
// ponytail: whitespace split, so a quoted dir with spaces or a `cd` before a relative dir misses; a shell parser if that bites.
export const claimOf = (command: string) => {
  // Shell separators (`;`, `&&`, `||`, `|`) end a word too, so `begin;` claims and `beginning` does not.
  const words = command.split(/\s+|[;&|]+/).filter(Boolean).map(w => w.replace(/^['"]|['"]$/g, ''))
  for (const { script, flag, file, kind } of CLAIMS) {
    const i = words.findIndex((w, i) => w.endsWith(script) && words[i + 2] === flag)
    if (i >= 0) return { kind, path: `${words[i + 1]!.replace(/\/+$/, '')}/${file}` }
  }
}

// Function declarations: the validator follows $ past an import into these only.
async function isOwner($: Dollar, kind: 'prompt' | 'wave', found?: string) {
  const mine = async (p: string) => (await $.fs.read(`${p}.owner`).catch(() => undefined))?.trim() === (await $.session.id())
  // The scripts write the .owner beside the file they claim, so a command claimOf cannot read (`python3 $S $D --start`) still claims.
  if (found !== undefined && (await mine(found))) return true
  const path = (await read($, owners))[kind]
  // A claim on another file than the one found is not ownership of it; Workstream dir + file, so `./ws`, `ws/.` and `//` match.
  // ponytail: last two segments only, so a claim on a same-named Workstream dir in another worktree counts as owning this one; resolve both paths against the project root to close it.
  const tail = (p: string) => p.split('/').filter(s => s && s !== '.').slice(-2).join('/')
  // A claim from inside the Workstream dir (`.`) has only the file segment: match on file name; the .owner read below still guards it.
  const same = (c: string, f: string) => c === f || (!c.includes('/') && f.endsWith(`/${c}`))
  if (!path || (found !== undefined && !same(tail(path), tail(found)))) return false
  return mine(path)
}

export function isPromptOwner($: Dollar, found?: string) {
  return isOwner($, 'prompt', found)
}
export function isWaveOwner($: Dollar, found?: string) {
  return isOwner($, 'wave', found)
}

export function registerOwner(on: Parameters<Register>[0]) {
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const ran = await next(e)
    const claim = claimOf(e.command)
    // A script's bad input exits 1 (isError); `FAIL:` also catches a pipe that hides the exit code.
    const ok = !ran.deny && !ran.isError && !ran.result.interrupted && !ran.result.backgroundTaskId && !ran.result.stdout.includes('FAIL:')
    if (claim && ok) {
      try {
        await $.fs.write(`${claim.path}.owner`, await $.session.id())
        await update($, owners, o => ({ ...o, [claim.kind]: claim.path }))
      } catch {
        // No claim recorded: the bands keep their last owner, the tool call stands.
      }
    }
    return ran
  })
}
