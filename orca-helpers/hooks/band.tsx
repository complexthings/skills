// The Wave band above the prompt: polls .orca/prompts/*/_status.json and
// draws the active Workstream's Waves and the current Wave's Work Items. In the
// Owning Session alone it also keeps the ambient signals: toasts, a status line
// entry and the Spinner word.

import { atom, read, update } from 'claude-code'
import type { EngineInterface as Dollar, FsEntry, Register } from 'claude-code'

import { allComplete, avatarArt, avatarMood, avatarState, doneSummary, spinnerWord, statusLine, toastStates, waveView } from './waves.ts'
import type { Item, Slot, Status } from './waves.ts'
import { FRAMES } from './assets/icons.ts'
import { HARNESSES, avatarManifest, interviewLive, pngImage, svgSource } from './prompt-band.tsx'
import { isWaveOwner } from './owner.ts'

const PROMPTS = '.orca/prompts'
const POLL_MS = 2000
const FRAME_MS = 400

// prompt-band.tsx reads the same ref, so `o` collapses or expands both.
const collapsed = atom({ plugin: 'orca-helpers', key: 'collapsed' } as const, false)
// The toast states last seen, kept across a reload so no toast repeats.
const toasted = atom({ plugin: 'orca-helpers', key: 'toasted' } as const, { workstream: '', keys: [] as string[] })

// The picked icons (art/icons/export.py): PNG frames the terminal reads from
// hooks/assets, the same pixels as SVG markup on the remote surfaces. With
// pictures off the terminal draws them as half-block Rasters (pngImage).
// `more` has no picked icon and keeps its Raster glyph, gray per theme.
const RGB = { grayDark: 0x959595, grayLight: 0x595959 }
const DEFAULT_BG = 0x01000000
const ORANGE = '#ff8700'
const WAVE_GLYPHS = ['▂▄', '▄▆', '▆▄', '▄▂']

type Icon = 'complete' | 'current' | 'upcoming' | 'orca' | 'more'
type Pictured = Exclude<Icon, 'more'>
const ROLE = { complete: 'check', current: 'wave', upcoming: 'upcoming', orca: 'orca' } as const
const frameOf = (icon: Pictured, frame: number) => frame % FRAMES[ROLE[icon]].length
const glyph = (icon: Pictured, frame: number) =>
  icon === 'complete' ? '✔ ' : icon === 'current' ? WAVE_GLYPHS[frame % WAVE_GLYPHS.length]! : icon === 'orca' ? '🐋' : '━━'

const cells = (text: string, color: number) =>
  (new Uint8Array(Uint32Array.from([...text].flatMap(c => [c.codePointAt(0)!, color, DEFAULT_BG])).buffer) as Uint8Array & { toBase64(): string }).toBase64()

const MORE_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path d="M8 3v10M3 8h10" stroke="gray" stroke-width="2"/></svg>'

const COLOR = { complete: 'gray', current: 'blue', upcoming: 'gray', more: 'gray' } as const

// Module state a reload rebuilds: the last status read, whether this session owns it,
// the icon's frame, the pinned Wave or Done tab, and the status line drawn (null: none set yet).
let status: Status | undefined
let owned = false
let pinned: number | 'done' | undefined
let line: string | undefined | null = null
let text: string | undefined
let frame = 0
let isLight = false

// Polls never overlap: a slow one would toast the same state twice.
// ponytail: a poll older than 30s is presumed hung and a new one proceeds; the hung one is not cancelled.
let polling = 0
let inflight: Promise<void> | undefined
// An overlapping caller gets the running poll, so startBand resolves only once status has loaded.
function poll($: Dollar) {
  if (polling && inflight && Date.now() - polling < 30_000) return inflight
  const mine = (polling = Date.now())
  const run = pollOnce($).finally(() => {
    if (polling === mine) {
      polling = 0
      inflight = undefined
    }
  })
  return (inflight = run)
}

async function pollOnce($: Dollar) {
  const dirs = await $.fs.list(PROMPTS).catch((): FsEntry[] => [])
  let found: Status | undefined
  let raw: string | undefined
  let path = ''
  for (const dir of dirs.filter(d => d.kind === 'dir')) {
    const file = `${PROMPTS}/${dir.name}/_status.json`
    const body = await $.fs.read(file).catch(() => undefined)
    if (body === undefined) continue
    try {
      const parsed: Status = JSON.parse(body)
      if (parsed.active) [found, raw, path] = [parsed, body, file]
    } catch {
      // set_status.py renames whole files in, so a bad parse is someone else's file.
    }
    if (found) break
  }
  const isOwned = found !== undefined && (await isWaveOwner($, path))
  const theme = (await $.config.list().catch(() => [])).find(row => row.key === 'theme')?.value
  isLight = String(theme ?? '').includes('light')
  if (raw !== text || isOwned !== owned) {
    // A new Workstream, or a run just finished, drops a pinned tab so Done can open.
    if (found?.workstream !== status?.workstream || (found && allComplete(found) && !(status && allComplete(status)))) pinned = undefined
    ;[status, text, owned] = [found, raw, isOwned]
    $.ui.invalidate('ui.render')
  }
  await signal($)
}

// The status line entry, cleared once --stop ends the run, and one toast per new
// toast state. A Workstream seen for the first time sets its states without toasts.
async function signal($: Dollar) {
  const entry = owned && status ? statusLine(status) : undefined
  if (entry !== line) {
    line = entry
    $.ui.status(entry)
  }
  // Not the owner: record the states without toasts, so regaining ownership repeats none.
  if (!status) return
  const s = status
  const states = toastStates(s)
  const keys = states.map(state => state.key)
  const last = await read($, toasted)
  if (owned && last.workstream === s.workstream) for (const state of states) if (!last.keys.includes(state.key)) $.ui.toast(state.text)
  if (last.workstream !== s.workstream || keys.join() !== last.keys.join()) await update($, toasted, () => ({ workstream: s.workstream, keys }))
}

// Each column's header tint, and the shown Wave's tab: one row with a backgroundColor, inverse in the
// terminal and a dark tint elsewhere, as the "A · Refined columns" artboards draw it.
const TINT = {
  terminal: {
    todo: { bg: '#3a3a3a', fg: '#ece9e4', item: '#8a8781' },
    progress: { bg: '#7d9bff', fg: '#0d0d0d', item: '#9fb4ff' },
    complete: { bg: '#5fc27e', fg: '#0d0d0d', item: '#7fd49a' },
  },
  desktop: {
    todo: { bg: '#2a2a2a', fg: '#ece9e4', item: '#cfccc6' },
    progress: { bg: '#26325a', fg: '#dfe6ff', item: '#c9d5ff' },
    complete: { bg: '#1f3527', fg: '#d4f2dc', item: '#a9dcb7' },
  },
} as const
const FAILED = { bg: '#3a1d1d', fg: '#ff9b94' }

// Draws the band; returns next(e) while no Workstream is active or an
// orca-prompt interview runs, so the Prompt Band shows in its place.
export function registerBand(on: Parameters<Register>[0]) {
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (status === undefined || !owned || interviewLive()) return next(e)
    const run = status
    // Once every Work Item is complete the Done tab follows the last Wave and opens by itself.
    const isDone = allComplete(run)
    const showDone = isDone && (pinned === undefined || pinned === 'done')
    const view = waveView(run, typeof pinned === 'number' ? pinned : undefined)
    const isCollapsed = await read($, collapsed)
    const isTerminal = e.surface === 'terminal'
    const { Box, Text, Button } = $.ui.resolve(e)
    const tints = TINT[isTerminal ? 'terminal' : 'desktop']
    // Step and Wave icons are 2x1 cells; the orca is 4x2 cells, 32 px elsewhere.
    const icon = async (key: string, kind: Icon) => {
      if (isTerminal) {
        const { Raster } = $.ui.resolve(e)
        if (kind === 'more') return <Raster key={key} columns={1} rows={1} cells={cells('+', isLight ? RGB.grayLight : RGB.grayDark)} />
        const [columns, rows] = kind === 'orca' ? [4, 2] : [2, 1]
        return pngImage($, e, key, `${$.plugin.root}/hooks/assets/${ROLE[kind]}_${frameOf(kind, frame)}.png`, columns, rows, glyph(kind, frame))
      }
      const { Svg } = $.ui.resolve(e)
      const source = kind === 'more' ? MORE_SVG : FRAMES[ROLE[kind]][frameOf(kind, frame)]!
      const size = kind === 'orca' ? 32 : 16
      return <Svg key={key} source={source} alt={kind} width={size} height={size} />
    }

    // The 24 px art: 4x2 cells of PNG frames in the terminal, 36 px SVG elsewhere.
    const avatar = async (item: Item) => {
      const key = `avatar-${item.id}`
      const harness = item.harness ?? 'claude'
      const state = avatarState(item.state)
      const mood = avatarMood(view.workstream, item.wave, run.items.filter(i => i.wave === item.wave).map(i => i.id), item.id)
      const manifest = await avatarManifest($)
      const art = avatarArt(HARNESSES[harness]?.art ?? harness, state, mood, manifest)
      const name = `${art}_${state}_${mood}_24`
      const i = frame % (manifest[name]?.frames ?? 1)
      if (isTerminal) {
        return pngImage($, e, key, `${$.plugin.root}/hooks/assets/avatars/${name}_${i}.png`, 4, 2, '● ')
      }
      const source = await svgSource($, `${$.plugin.root}/hooks/assets/avatars/${name}_${i}.svg`)
      if (!source) return null
      const { Svg } = $.ui.resolve(e)
      return <Svg key={key} source={source} alt={harness} width={36} height={36} />
    }

    // Each Wave is a tab: a press pins its columns, a second press returns to the current Wave.
    const press = (wave: number | 'done') => {
      pinned = pinned === wave ? undefined : wave
      $.ui.invalidate('ui.render')
    }
    const slot = async (s: Slot) => {
      if ('more' in s) {
        return (
          <Box key="more">
            {await icon('icon-more', 'more')}
            <Text color="gray">{s.more} More Waves</Text>
          </Box>
        )
      }
      const label = isTerminal ? `W${s.wave} ${s.complete}/${s.total}` : `Wave ${s.wave} · ${s.complete}/${s.total}`
      const isShown = !showDone && s.wave === view.shown
      return (
        <Box key={`tab-${s.wave}`} gap={1}>
          {await icon(`icon-${s.wave}`, s.kind)}
          <Button key={`wave-${s.wave}`} plain label={label} onPress={() => press(s.wave)}>
            <Text color={isShown ? tints.progress.fg : COLOR[s.kind]} backgroundColor={isShown ? tints.progress.bg : undefined}>
              {isShown ? ` ${label} ` : label}
            </Text>
          </Button>
        </Box>
      )
    }

    const doneTab = async () => (
      <Box key="tab-done" gap={1}>
        {await icon('icon-done', 'complete')}
        <Button key="wave-done" plain label="Done" onPress={() => press('done')}>
          <Text color={showDone ? tints.complete.fg : COLOR.complete} backgroundColor={showDone ? tints.complete.bg : undefined}>
            {showDone ? ' Done ' : 'Done'}
          </Text>
        </Button>
      </Box>
    )

    const row = async (item: Item, color: string, text: string) => (
      <Box key={item.id} gap={1} alignItems="center">
        {await avatar(item)}
        <Text color={color}>{text}</Text>
      </Box>
    )

    // Outer border and padding take 4 cells; two gaps sit between three columns.
    const inner = e.props.bodyColumns - 4
    const width = Math.max(12, Math.floor((inner - 2) / 3))
    const column = async (key: string, heading: string, items: Item[], tint: (typeof tints)[keyof typeof tints]) => (
      <Box key={key} flexDirection="column" width={width}>
        <Box backgroundColor={tint.bg} justifyContent="space-between" paddingX={1}>
          <Text color={tint.fg} bold>
            {isTerminal ? heading.toUpperCase() : heading}
          </Text>
          <Text color={tint.fg}>{items.length}</Text>
        </Box>
        {await Promise.all(
          items.map(async item =>
            // A failed item stays in its lane, red, with its reason.
            item.state === 'failed'
              ? <Box key={item.id} backgroundColor={FAILED.bg}>{await row(item, FAILED.fg, `! ${item.title}: ${item.reason ?? 'failed'}`)}</Box>
              : row(item, tint.item, item.title),
          ),
        )}
      </Box>
    )

    // The G Done card: the run time, every Harness Avatar, and the PRs merged.
    const donePanel = async () => {
      const { merged, badge } = doneSummary(run)
      return (
        <Box flexDirection="column" gap={1}>
          <Text color={tints.complete.fg} backgroundColor={tints.complete.bg}>
            {` ${badge} `}
          </Text>
          <Box flexWrap="wrap" gap={1}>
            {await Promise.all(run.items.map(avatar))}
          </Box>
          <Box gap={1}>
            <Box width={10} flexShrink={0}>
              <Text dimColor>Merged</Text>
            </Box>
            <Text>{merged}</Text>
          </Box>
        </Box>
      )
    }

    return (
      <Box flexDirection="column" borderStyle="round" paddingX={1}>
        <Box justifyContent="space-between" alignItems="center">
          <Box gap={1} alignItems="center">
            {await icon('icon-orca', 'orca')}
            {/* One 1-row Box beside the 2-row orca, so the name and every tab center as one row. */}
            <Box key="header-row" gap={1}>
              <Text color={ORANGE} bold>
                {view.workstream}
              </Text>
              <Text>│</Text>
              {await Promise.all(view.slots.map(slot))}
              {isDone ? await doneTab() : null}
            </Box>
          </Box>
          <Button
            key="caret"
            plain
            hotkey="o"
            label={isCollapsed ? '⌃' : '⌄'}
            onPress={() => update($, collapsed, c => !c)}
          />
        </Box>
        {isCollapsed ? null : showDone ? (
          await donePanel()
        ) : (
          <Box flexDirection="column">
            <Box gap={1}>
              {await column('todo', 'To do', view.todo, tints.todo)}
              {await column('in-progress', 'In progress', [...view.failed, ...view.inProgress], tints.progress)}
              {await column('complete', 'Complete', view.complete, tints.complete)}
            </Box>
          </Box>
        )}
      </Box>
    )
  })

  // The Spinner's word reads the current Wave's progress while a run is on.
  on('ui.render', { component: 'Spinner' }, async ($, e, next) =>
    status === undefined || !owned ? next(e) : next({ ...e, props: { ...e.props, word: spinnerWord(status) } }),
  )
}

// True while the band draws in the Prompt Band's place; its ticker skips then.
export const waveActive = () => status !== undefined && owned && !interviewLive()

// Starts the 2 s poll and the in-progress icon's animation; session.start calls it.
export function startBand($: Dollar) {
  $.clock.every(POLL_MS, () => poll($))
  $.clock.every(FRAME_MS, () => {
    if (!waveActive()) return
    frame += 1
    $.ui.invalidate('ui.render')
  })
  return poll($)
}
