// Two hooks for Orca Workstreams: a guard that keeps _status.json files
// written only by set_status.py and _prompt-band.json only by
// set_prompt_band.py, and a session-start check that the stored
// Prompt Settings still name models their Priority File carries.

const STATUS_FILE = /(^|\/)\.orca\/prompts\/(.+\/)?[^/]*_status\.json$/
const BAND_FILE = /(^|\/)\.orca\/prompts\/_prompt-band\.json$/
const SETTINGS_PATH = '.orca/prompts/prompt-settings.json'

// Agent Harness -> its fixed provider set in the Priority File. The discovered
// harnesses (pi, opencode, copilot, agy) are absent: list_models.py ranks
// them and the Priority File is never their whitelist.
const PROVIDERS = { claude: 'anthropic', codex: 'openai-codex' }
// The Priority Files rank no models for the Main Orchestrator of their own.
const SLOT_RANKINGS = { mainOrchestrator: 'orchestrationWorker' }

/** The script that alone writes `path`, or undefined for any other file. @param {string} path */
export const writerOf = path => {
  const posix = path.replaceAll('\\', '/')
  return STATUS_FILE.test(posix) ? 'set_status.py' : BAND_FILE.test(posix) ? 'set_prompt_band.py' : undefined
}

/**
 * The Model Slots naming a model the Priority File does not rank for that slot,
 * as `harness.slot: model` — the check orca-prompt Round 2 makes.
 * @param {any} settings @param {any} priority @returns {string[]}
 */
export const staleModels = (settings, priority) =>
  (settings.harnesses ?? []).flatMap(harness => {
    const provider = priority.modelOrder?.[PROVIDERS[harness.name]]
    if (provider === undefined) return []
    return Object.entries(harness.models ?? {}).flatMap(([slot, chosen]) => {
      const ranked = provider[SLOT_RANKINGS[slot] ?? slot] ?? []
      // A slot is a plain model id or {model, effort}; `.` and `-` are one in an id.
      const model = typeof chosen === 'string' ? chosen : chosen?.model
      const same = id => id.replaceAll('.', '-')
      return model && !ranked.some(entry => same(entry.model) === same(model))
        ? [`${harness.name}.${slot}: ${model}`]
        : []
    })
  })

/** @param {Parameters<import('claude-code').Register>[0]} on */
export function registerGuards(on) {
  for (const tool of /** @type {const} */ (['Edit', 'Write'])) {
    on('tool.call', { tool }, ($, e, next) => {
      const writer = writerOf(e.file_path)
      return writer
        ? { deny: `${$.plugin.name}: ${e.file_path} is written by ${writer} only. Run ${writer} instead of editing it.` }
        : next(e)
    }).catch(($, e, next) =>
      next.called ? next(e) : { deny: `${$.plugin.name}: its _status.json / _prompt-band.json guard failed.` },
    )
  }
}

/**
 * Shows one warning line when the stored Prompt Settings name a model their
 * Priority File does not rank. No stored settings is the ordinary first run.
 * @param {import('claude-code').Dollar} $
 */
export async function warnStaleSettings($) {
  try {
    const text = await $.fs.read(SETTINGS_PATH).catch(() => undefined)
    if (text === undefined) return

    const settings = JSON.parse(text)
    const name = settings.priorityFile
    // As written first, then a file name in the plugin's own data/, as _priority_path does.
    const priority = JSON.parse(
      await $.fs.read(name).catch(() => $.fs.read(`${$.plugin.root}/skills/orca-prompt/data/${name}`)),
    )
    const stale = staleModels(settings, priority)
    if (stale.length > 0) {
      $.ui.log(`${$.plugin.name}: ${SETTINGS_PATH} names models ${name} does not rank (${stale.join(', ')}). Run orca-prompt-settings to re-pick them.`)
    }
  } catch {
    // Malformed settings or a missing Priority File: nothing to warn about.
  }
}
