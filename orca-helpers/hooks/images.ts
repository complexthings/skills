// Pictures off: Claude Code in a plain Orca terminal draws every band Image as
// its alt text, because only an Orca-launched agent gets
// CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1. A toast in every such session names the
// fix, and /orca-images writes it to the shell file. The fix is per machine, so
// the toast does not wait for the Owning Session (ADR 0012).
import { atom, read, update } from 'claude-code'
import type { EngineInterface as Dollar, Register } from 'claude-code'

export const COMMENT = '# orca-helpers /orca-images: let Claude Code draw pictures in an Orca terminal'
export const LINE = '[[ $TERM_PROGRAM == Orca ]] && export CLAUDE_CODE_FORCE_TERMINAL_IMAGES=1'
const SHELL_FILES: Record<string, string> = { zsh: '.zshrc', bash: '.bashrc' }

// Kept in $.state, so a reload repeats no toast.
const toasted = atom({ plugin: 'orca-helpers', key: 'imagesToasted' } as const, false)

export async function imagesOff($: Dollar) {
  return (await $.env.get('TERM_PROGRAM')) === 'Orca' && (await $.env.get('CLAUDE_CODE_FORCE_TERMINAL_IMAGES')) !== '1'
}

export async function toastImagesOff($: Dollar) {
  if (!(await imagesOff($)) || (await read($, toasted))) return
  await update($, toasted, () => true)
  $.ui.toast(`${$.plugin.name}: pictures are off in this Orca terminal. Run /orca-images to fix it, then restart Claude.`)
}

export function registerImages(on: Parameters<Register>[0]) {
  on('command.run', { command: 'orca-images' }, async $ => {
    const shell = ((await $.env.get('SHELL')) ?? '').split('/').pop() ?? ''
    const name = SHELL_FILES[shell]
    if (name === undefined) return { text: `Add this line to your shell's startup file, then restart Claude:\n\n${LINE}` }

    const file = `${await $.env.get('HOME')}/${name}`
    // A missing file is a shell file not written yet.
    const text = await $.fs.read(file).catch(() => '')
    if (text.split('\n').includes(LINE)) return { text: `${file} already has the line. Restart Claude to draw pictures.` }
    await $.fs.write(file, `${text}${text === '' || text.endsWith('\n') ? '' : '\n'}\n${COMMENT}\n${LINE}\n`)
    return { text: `Added the line to ${file}. Restart Claude to draw pictures.` }
  })
}
