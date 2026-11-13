// The one hooks module: the guards from guards.js, the Owning Session, the Wave band, the Prompt Band, Attention capture and /orca-images.
import type { EngineInterface as Dollar, Register } from 'claude-code'

import { registerAttention } from './attention.ts'
import { registerBand, startBand } from './band.tsx'
import { registerImages, toastImagesOff } from './images.ts'
import { registerOwner } from './owner.ts'
import { hidePromptBand, registerPromptBand, startPromptBand } from './prompt-band.tsx'
import { registerGuards, warnStaleSettings } from './guards.js'

// Both bands' polls, started once: by session.start, or by the first band
// draw where the module loads after session.start has fired (a Desktop session).
let started: Promise<void> | undefined
const start = ($: Dollar) => (started ??= Promise.all([startBand($), startPromptBand($)]).then(() => {}))

export const register: Register = on => {
  registerGuards(on)
  registerOwner(on)
  registerBand(on)
  registerPromptBand(on)
  registerImages(on)
  registerAttention(on)

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    await start($)
    return next(e)
  })

  on('session.start', async ($, e, next) => {
    const result = await next(e)
    await $.command.register({ name: 'orca-images', description: 'Let Claude Code draw pictures in an Orca terminal' })
    await start($)
    // No prompts yet is a fresh startup; a resume or a reload keeps the Prompt Band.
    if ((await $.session.turns()) === 0) await hidePromptBand($)
    await warnStaleSettings($, e.cwd)
    await toastImagesOff($)
    return result
  })

  on('session.end', async ($, e, next) => {
    if (e.reason === 'clear') await hidePromptBand($)
    return next(e)
  })
}
