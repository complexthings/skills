// The Prompt Band above the prompt: polls .orca/prompts/_prompt-band.json, as
// set_prompt_band.py writes it, and follows the orca-prompt interview step by
// step with the picked icons and the Harness Avatars.

import { atom, read, update } from 'claude-code'
import type { EngineInterface as Dollar, Register } from 'claude-code'

import { FRAMES } from './assets/icons.ts'
import { waveActive } from './band.tsx'
import { imagesOff } from './images.ts'
import { isPromptOwner } from './owner.ts'

const FILE = '.orca/prompts/_prompt-band.json'
const POLL_MS = 2000
const FRAME_MS = 200
const HOLD_MS = 3000

// The Wave Band's atom: one ref, one value, so `o` collapses or expands both.
const collapsed = atom({ plugin: 'orca-helpers', key: 'collapsed' } as const, false)

type StepId = 'basics' | 'harness' | 'models' | 'timing' | 'write-validate'
type Step = { id: StepId; title: string; state: 'upcoming' | 'active' | 'complete'; answers: Record<string, any> }
type Band = { updatedAt?: string; step: StepId | null; ended: boolean; steps: Step[]; checklist: { id: string; title: string; done: boolean }[] }
type Slot = string | { model: string; effort?: string | null } | null | undefined

type AvatarState = 'default' | 'selected' | 'main' | 'disabled' | 'writing' | 'waiting'
const AVATAR = { name: 'avatar', columns: 9, rows: 5 } as const
export const HARNESSES: Record<string, { title: string; art: string }> = {
  claude: { title: 'Claude Code', art: 'claude' },
  copilot: { title: 'Copilot', art: 'copilot' },
  opencode: { title: 'OpenCode', art: 'opencode' },
  codex: { title: 'Codex', art: 'codex' },
  pi: { title: 'Pi', art: 'pi' },
  agy: { title: 'Antigravity', art: 'antigravity' },
}
const harnessTitle = (name: string) => HARNESSES[name]?.title ?? name

const EFFORT: Record<string, string> = { max: 'MX', xhigh: 'XH', high: 'H', medium: 'M', low: 'L' }
const INTEGRATION: Record<string, string> = { commit: 'Commit', branch: 'Branch', pr: 'PR', 'pr-merge': 'PR + merge' }
const SCOPE_FROM: Record<string, string> = { interview: 'Interview Me Now', written: 'Already Written' }
const MODEL_SLOTS = [
  ['Orchestrator', 'mainOrchestrator'],
  ['Worker', 'orchestrationWorker'],
  ['Subagent', 'subagent'],
  ['Simple', 'subagentSimple'],
] as const

// `claude-opus-5-5` reads `Opus 5.5`, `gpt-6.1-sol` reads `GPT 6.1 Sol`.
export const modelLabel = (slot: Slot) => {
  if (!slot) return '—'
  const { model, effort } = typeof slot === 'string' ? { model: slot, effort: null } : slot
  const words = model.replace(/^claude-/, '').split(/[-_/]/)
  const name = words
    .reduce<string[]>((out, w) => (/^\d+$/.test(w) && /\d$/.test(out.at(-1) ?? '') ? [...out.slice(0, -1), `${out.at(-1)}.${w}`] : [...out, w]), [])
    .map(w => (w === 'gpt' ? 'GPT' : w[0]!.toUpperCase() + w.slice(1)))
    .join(' ')
  return effort ? `${name} (${EFFORT[effort] ?? effort})` : name
}

// Module state a reload rebuilds: the last band read, the frame, the held and
// pinned panels, and the band file a startup or /clear hid.
let band: Band | undefined
let text: string | undefined
let frame = 0
let held: StepId | undefined
let holdToken = 0
let pinned: StepId | 'ready' | undefined
let hiddenText: string | undefined
// Whether this session is the Owning Session of the band file; every other session draws nothing.
let owned = false

async function poll($: Dollar) {
  const isOwned = await isPromptOwner($, FILE)
  if (isOwned !== owned) {
    owned = isOwned
    $.ui.invalidate('ui.render')
  }
  const raw = await $.fs.read(FILE).catch(() => undefined)
  if (raw === text) return
  let next: Band | undefined
  try {
    next = raw === undefined ? undefined : JSON.parse(raw)
  } catch {
    // set_prompt_band.py renames whole files in, so a bad parse is someone else's file.
    return
  }
  // A step change holds the step left behind on screen for HOLD_MS.
  if (band?.step && next?.step && next.step !== band.step) {
    held = band.step
    const token = ++holdToken
    $.clock.after(HOLD_MS, () => {
      if (token !== holdToken) return
      held = undefined
      $.ui.invalidate('ui.render')
    })
  }
  // Any accepted write to the band file unpins: the caret and `o` live in the pinned
  // panel, so a pin that fails to render must clear without waiting for a step change.
  pinned = undefined
  config = undefined
  ;[band, text] = [next, raw]
  $.ui.invalidate('ui.render')
}

// The band shows until a startup or /clear hides what the file holds then;
// a later write to the file shows it again.
const isHidden = () => !owned || band === undefined || text === hiddenText

// An interview runs from the band's first write to `end`; the Wave Band gives
// way to it until then, and takes the place back after. An interrupted one never
// writes `end`, so a band untouched for STALE_MS no longer counts (no `updatedAt`
// is an old file, live).
const STALE_MS = 30 * 60 * 1000
export const interviewLive = () =>
  !isHidden() && !band!.ended && (!band!.updatedAt || Date.now() - Date.parse(band!.updatedAt) < STALE_MS)

// Orca reads no kitty image file outside the workspace and the temp folders,
// and the plugin root sits in neither, so the terminal gets each PNG's bytes,
// read once. An unreadable PNG draws its alt as text.
const pngs = new Map<string, Promise<string | undefined>>()
export async function pngSource($: Dollar, file: string) {
  if (!pngs.has(file)) pngs.set(file, $.fs.read(file, { as: 'bytes' }).then(b => b.base64, () => undefined))
  const png = await pngs.get(file)!
  if (png === undefined) pngs.delete(file) // a failed read retries on the next render
  return png === undefined ? undefined : { png }
}

// One frame's SVG, read once. The Svg source is capped at 131072 chars, so each
// frame is its own file. An unreadable file is undefined and retries on the next render.
const svgs = new Map<string, Promise<string | undefined>>()
export async function svgSource($: Dollar, path: string) {
  if (!svgs.has(path)) svgs.set(path, $.fs.read(path).then(s => s, () => undefined))
  const svg = await svgs.get(path)!
  if (svg === undefined) svgs.delete(path)
  return svg
}

// The avatar manifest holds each strip's frame count. Only a good read is kept;
// a failed one is {} for this call and retries on the next render.
let manifest: Record<string, { frames: number }> | undefined
export async function avatarManifest($: Dollar) {
  manifest ??= await $.fs
    .read(`${$.plugin.root}/hooks/assets/avatars/manifest.json`)
    .then(body => JSON.parse(body), () => undefined)
  return manifest ?? {}
}

// Pictures off, the PNG draws as half-block cells (art/icons/cells.py) of the same size,
// read as svgSource reads text; an unreadable cells file draws the alt.
export async function pngImage($: Dollar, e: Parameters<Dollar['ui']['resolve']>[0], key: string, file: string, columns: number, rows: number, alt: string) {
  const { Image, Raster, Text } = $.ui.resolve(e)
  if (await imagesOff($)) {
    const cells = await svgSource($, file.replace(/\.png$/, `.${columns}x${rows}.cells`))
    return cells ? <Raster key={key} columns={columns} rows={rows} cells={cells} /> : <Text key={key}>{alt}</Text>
  }
  const source = await pngSource($, file)
  return source ? <Image key={key} source={source} columns={columns} rows={rows} alt={alt} /> : <Text key={key}>{alt}</Text>
}

export async function hidePromptBand($: Dollar) {
  await poll($)
  hiddenText = text
  $.ui.invalidate('ui.render')
}

// The Ready tab reads the Workstream's _config.json, once per band write: Work
// Items per Wave, each on the Agent Harness scaffold.py's route_harness picks.
type Config = {
  workstream?: string
  targetBranch?: string
  integration?: string
  harnesses?: { name: string; tier: string }[]
  workItems?: { id: string; size: string; wave: number }[]
}
const TIERS = ['light', 'standard']
const routeHarness = (size: string, harnesses: { name: string; tier: string }[]) => {
  const distance = (h: { tier: string }) => Math.abs(TIERS.indexOf(h.tier) - TIERS.indexOf(size))
  return harnesses.reduce((best, h) => (distance(h) < distance(best) ? h : best))
}
let config: Promise<Config | undefined> | undefined
const readConfig = ($: Dollar, workstream: string) => {
  config ??= $.fs.read(`.orca/prompts/${workstream}/_config.json`).then(
    body => JSON.parse(body) as Config,
    () => undefined,
  )
  return config.then(c => {
    if (c === undefined) config = undefined // a failed read retries on the next render
    return c
  })
}

// "Waves 1: 3 Work Items · Claude Code, Pi", one line per Wave in order.
export const waveLines = (c: Config) => {
  const waves = new Map<number, { count: number; names: string[] }>()
  for (const wi of [...(c.workItems ?? [])].sort((x, y) => x.wave - y.wave)) {
    const w = waves.get(wi.wave) ?? { count: 0, names: [] }
    const name = c.harnesses?.length ? harnessTitle(routeHarness(wi.size, c.harnesses).name) : undefined
    w.count += 1
    if (name && !w.names.includes(name)) w.names.push(name)
    waves.set(wi.wave, w)
  }
  return [...waves].map(([wave, w]) => ({
    wave,
    text: [`${w.count} Work Item${w.count === 1 ? '' : 's'}`, w.names.join(', ')].filter(Boolean).join(' · '),
  }))
}

// The question dialog's rows on the terminal, counted as the engine counts a
// text: a row to the line and one more for each 40 columns.
const QUESTION_ROWS = 12
const textRows = (s: string) => Math.max(1, Math.ceil(s.length / 40))

type Tab = StepId | 'ready'

export function registerPromptBand(on: Parameters<Register>[0]) {
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (isHidden()) return next(e)
    const b = band!
    const isCollapsed = await read($, collapsed)
    const { Box, Text, Button } = $.ui.resolve(e)
    const answers = (id: StepId) => b.steps.find(s => s.id === id)?.answers ?? {}

    // The terminal draws PNG frames; the remote surfaces the same pixels as SVG.
    const icon = async (key: string, role: keyof typeof FRAMES, n: number, alt: string, columns = 2, rows = 1) => {
      const i = n % FRAMES[role].length
      if (e.surface === 'terminal') {
        return pngImage($, e, key, `${$.plugin.root}/hooks/assets/${role}_${i}.png`, columns, rows, alt)
      }
      const { Svg } = $.ui.resolve(e)
      return <Svg key={key} source={FRAMES[role][i]!} alt={alt} width={rows * 16} height={rows * 16} />
    }
    const avatar = async (key: string, harness: string, state: AvatarState) => {
      const art = HARNESSES[harness]?.art ?? 'claude'
      const i = frame % ((await avatarManifest($))[`${art}_${state}`]?.frames ?? 1)
      if (e.surface === 'terminal') {
        return pngImage($, e, key, `${$.plugin.root}/hooks/assets/avatars/${art}_${state}_${i}.png`, AVATAR.columns, AVATAR.rows, harnessTitle(harness))
      }
      const path = `${$.plugin.root}/hooks/assets/avatars/${art}_${state}_${i}.svg`
      const source = await svgSource($, path)
      if (!source) return <Text key={key}>{harnessTitle(harness)}</Text>
      const { Svg } = $.ui.resolve(e)
      return <Svg key={key} source={source} alt={harnessTitle(harness)} width={48} height={53} />
    }

    const field = (key: string, label: string, value: unknown) => (
      <Box key={key} width={44} gap={1}>
        <Box width={16} flexShrink={0}>
          <Text color="blue" bold>
            {label}
          </Text>
        </Box>
        <Text wrap="truncate-end">{value === undefined || value === null ? '' : String(value)}</Text>
      </Box>
    )

    const main = String(answers('harness').mainOrchestratorHarness ?? 'claude')
    const selected: { name: string; tier?: string }[] = answers('harness').harnesses ?? []
    const at = (id: Tab) => (id === 'ready' ? b.steps.length : b.steps.findIndex(s => s.id === id))

    // Every answer up to the shown step, two to a row.
    const fields: Record<StepId, () => [string, unknown][]> = {
      basics: () => {
        const a = answers('basics')
        return [
          ['Workstream', a.workstream],
          ['Integration', INTEGRATION[a.integration] ?? a.integration],
          ['Target branch', a.targetBranch],
          ['Tickets', a.tickets === undefined ? undefined : a.tickets ? 'Yes' : 'No'],
          ['Scope from', SCOPE_FROM[a.scopeFrom] ?? a.scopeFrom],
        ]
      },
      harness: () => [],
      // Concurrency and the Model Slots draw in their own column; see modelColumn.
      models: () => {
        const a = answers('models')
        return [['Model set', a.modelSet === 'seeded' ? 'Seeded' : a.modelSet === 'opinionated' ? 'Opinionated' : undefined]]
      },
      timing: () => {
        const a = answers('timing')
        if (a.mode === 'now') return [['Runs', 'Now']]
        if (a.mode !== 'later') return [['Runs', 'Now, or schedule for later?']]
        return [
          ['Scheduled for', `${a.localTime ?? ''} ${a.timezone ?? ''}`.trim()],
          ['UTC', a.utcTime],
        ]
      },
      'write-validate': () => [],
    }

    const answersPanel = async (shown: StepId) => {
      const upTo = at(shown)
      const harnessAt = at('harness')
      const mood: AvatarState | undefined = shown === 'timing' && answers('timing').mode === 'later' ? 'waiting' : shown === 'write-validate' && !b.ended ? 'writing' : undefined
      const detected: string[] = answers('harness').detected ?? selected.map(s => s.name)
      const names = detected.length ? detected : Object.keys(HARNESSES)
      const avatars =
        upTo < harnessAt
          ? null
          : await Promise.all(
              names.map(async name => {
                const pick = selected.find(s => s.name === name)
                const state: AvatarState = name === main && pick ? (mood ?? 'main') : pick ? 'selected' : 'disabled'
                return (
                  <Box key={`harness-${name}`} flexDirection="column" alignItems="center" width={11}>
                    {await avatar(`avatar-${name}`, name, state)}
                    {name === main && pick ? <Text color="blue">Main</Text> : <Text dimColor={!pick}>{harnessTitle(name)}</Text>}
                  </Box>
                )
              }),
            )
      const rows = b.steps.slice(0, upTo + 1).flatMap(s => fields[s.id]())
      // Concurrency, then each harness's Model Slots one to a line, untruncated, at the right.
      const m = answers('models')
      const models: Record<string, Record<string, Slot>> = m.models ?? {}
      const modelColumn =
        upTo < at('models') ? null : (
          <Box flexDirection="column" flexShrink={0}>
            {field('field-concurrency', 'Concurrency', m.maxConcurrency)}
            {Object.entries(models).map(([name, slots]) => (
              <Box key={`models-${name}`} gap={1}>
                <Box width={16} flexShrink={0}>
                  <Text color="blue" bold>
                    {harnessTitle(name)}
                  </Text>
                </Box>
                <Box flexDirection="column">
                  {MODEL_SLOTS.map(([label, slot]) => (
                    <Text key={`model-${name}-${slot}`}>{`${label} ${modelLabel(slots[slot])}`}</Text>
                  ))}
                </Box>
              </Box>
            ))}
          </Box>
        )
      return (
        <Box flexDirection="column" gap={1}>
          {avatars ? <Box flexWrap="wrap">{avatars}</Box> : null}
          <Box flexWrap="wrap" columnGap={2}>
            <Box flexWrap="wrap" columnGap={2} width={90}>
              {rows.map(([label, value], i) => field(`field-${i}`, label, value))}
            </Box>
            {modelColumn}
          </Box>
          {shown === 'write-validate' ? (
            <Box flexDirection="column">
              {b.checklist.map(item => (
                <Text key={`check-${item.id}`} color={item.done ? 'green' : 'gray'}>
                  {item.done ? '✔' : '○'} {item.title}
                </Text>
              ))}
            </Box>
          ) : null}
        </Box>
      )
    }

    // The G Ready card: what orca-execute will run, read from _config.json.
    const readyPanel = async () => {
      const a = answers('basics')
      const t = answers('timing')
      const c = a.workstream ? await readConfig($, String(a.workstream)) : undefined
      const workstream = String(c?.workstream ?? a.workstream ?? '')
      const target = c?.targetBranch ?? a.targetBranch ?? ''
      const integration = c?.integration ?? a.integration
      const lands = integration === 'branch' ? `Branch off ${target}` : `${INTEGRATION[integration] ?? integration ?? ''} into ${target}`
      const scheduled = t.mode === 'later' ? `${t.localTime ?? ''} ${t.timezone ?? ''}`.trim() : undefined
      const row = (key: string, label: string, value: string) => (
        <Box key={key} gap={1}>
          <Box width={10} flexShrink={0}>
            <Text dimColor>{label}</Text>
          </Box>
          <Text>{value}</Text>
        </Box>
      )
      return (
        <Box flexDirection="column" gap={1}>
          <Box gap={1}>
            <Text color="claude" bold>
              {workstream}
            </Text>
            <Text color="blue"> Ready </Text>
          </Box>
          <Box flexDirection="column">
            {c ? waveLines(c).map(w => row(`wave-${w.wave}`, `Wave ${w.wave}`, w.text)) : row('waves', 'Waves', `no .orca/prompts/${workstream}/_config.json`)}
            {row('lands', 'Lands as', lands)}
            {row('runs', 'Runs', scheduled ? `Scheduled ${scheduled}` : 'Now')}
          </Box>
          <Text color="blue">{scheduled ? `Next: nothing to run, it starts at ${scheduled}` : `Next: run /orca-execute ${workstream}`}</Text>
        </Box>
      )
    }

    // The flag stands for Write / Validate in every state, moving only while it runs.
    const stepIcon = (s: Step) => {
      const running = s.state === 'active' && !b.ended
      if (s.id === 'write-validate') return icon(`icon-${s.id}`, 'flag', running ? frame : 0, '▚▞')
      if (s.state === 'complete') return icon(`icon-${s.id}`, 'check', 0, '✔ ')
      if (s.state === 'active') return icon(`icon-${s.id}`, 'wave', frame, '▂▄')
      return icon(`icon-${s.id}`, 'upcoming', 0, '━━')
    }

    // A finished step, and Ready once `end` writes, is a tab that pins its panel.
    const shown: Tab = pinned ?? held ?? (b.ended ? 'ready' : (b.step ?? 'basics'))
    const tab = (id: Tab, title: string, color: string, clickable: boolean, dim = false) => {
      const label = (
        <Text color={id === shown ? 'blue' : color} bold={id === shown} dimColor={dim && id !== shown}>
          {title}
        </Text>
      )
      if (!clickable) return label
      const press = () => {
        pinned = pinned === id ? undefined : id
        $.ui.invalidate('ui.render')
      }
      return (
        <Button key={`step-${id}`} plain label={title} onPress={press}>
          {label}
        </Button>
      )
    }
    const stepRow = async (s: Step) => (
      <Box key={`row-${s.id}`} gap={1} backgroundColor={s.id === shown ? '#26325a' : undefined}>
        {await stepIcon(s)}
        {tab(s.id, s.title, s.state === 'active' && !b.ended ? 'blue' : 'gray', s.state === 'complete', s.state === 'upcoming')}
      </Box>
    )

    const header = (
      <Box key="header" justifyContent="space-between">
        <Box gap={1} alignItems="center">
          {await icon('icon-orca', 'orca', frame, '◖◗', 4, 2)}
          <Text color="claude" bold>
            Orca Prompt
          </Text>
          {isCollapsed ? <Text color="blue">▶ {shown === 'ready' ? 'Ready' : b.steps[at(shown)]?.title}</Text> : null}
        </Box>
        <Button key="caret" plain hotkey="o" label={isCollapsed ? '⌃' : '⌄'} onPress={() => update($, collapsed, c => !c)} />
      </Box>
    )
    if (isCollapsed) {
      return (
        <Box flexDirection="column" borderStyle="round" paddingX={1}>
          {header}
        </Box>
      )
    }
    return (
      <Box flexDirection="column" borderStyle="round" paddingX={1}>
        {header}
        <Box gap={2}>
          <Box flexDirection="column" width={24} flexShrink={0}>
            {await Promise.all(b.steps.map(stepRow))}
            {b.ended ? (
              <Box key="row-ready" gap={1} backgroundColor={shown === 'ready' ? '#26325a' : undefined}>
                {await icon('icon-ready', 'check', 0, '✔ ')}
                {tab('ready', 'Ready', 'gray', true)}
              </Box>
            ) : null}
          </Box>
          <Box flexDirection="column" flexGrow={1}>
            {shown === 'ready' ? await readyPanel() : await answersPanel(shown)}
          </Box>
        </Box>
      </Box>
    )
  })

  // H1: one strip above the engine's question while an interview runs, since the
  // dialog takes the band's place in the terminal.
  on('ui.render', { component: 'AskUserQuestion' }, async ($, e, next) => {
    if (!interviewLive()) return next(e)
    const b = band!
    const { Box, Text } = $.ui.resolve(e)
    const mark = (s: Step) => (s.state === 'complete' ? '✔' : s.state === 'active' ? '▶' : '·')
    const steps = b.steps.map(s => `${mark(s)} ${s.title}`).join(' ')
    if (textRows('Orca Prompt') + textRows(steps) > QUESTION_ROWS) return next(e)
    const orca = async () => {
      if (e.surface === 'terminal') return pngImage($, e, 'strip-orca', `${$.plugin.root}/hooks/assets/orca_0.png`, 2, 1, '◖◗')
      const { Svg } = $.ui.resolve(e)
      return <Svg key="strip-orca" source={FRAMES.orca[0]!} alt="Orca" width={16} height={16} />
    }
    return (
      <Box flexDirection="column">
        <Box key="strip" gap={1}>
          {await orca()}
          <Text color="claude" bold>
            Orca Prompt
          </Text>
          <Text wrap="truncate-end">
            {b.steps.map(s => (
              <Text key={`strip-${s.id}`} color={s.state === 'active' ? 'blue' : 'gray'} bold={s.state === 'active'}>
                {mark(s)} {s.title}{' '}
              </Text>
            ))}
          </Text>
        </Box>
        {await next(e)}
      </Box>
    )
  })
}

// Starts the 2 s poll and the icons' and avatars' animation; session.start calls it.
export function startPromptBand($: Dollar) {
  $.clock.every(POLL_MS, () => poll($))
  $.clock.every(FRAME_MS, () => {
    if (isHidden() || waveActive()) return
    frame += 1
    $.ui.invalidate('ui.render')
  })
  return poll($)
}
