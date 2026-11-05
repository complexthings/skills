// What more than one Board element draws: the Harness Avatar, the spotlight card, number formats and the tabs.
import { Tabs } from '@radix-ui/themes'
import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState, type PointerEvent, type ReactNode } from 'react'
import type { Usage } from './types'

type Manifest = Record<string, { frames: number; ms: number[] }>

const FRAME_MS = 400
export const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches

// The same names and art as HARNESSES in hooks/prompt-band.tsx.
export const HARNESSES: Record<string, { title: string; art: string }> = {
  claude: { title: 'Claude Code', art: 'claude' },
  copilot: { title: 'Copilot', art: 'copilot' },
  opencode: { title: 'OpenCode', art: 'opencode' },
  codex: { title: 'Codex', art: 'codex' },
  pi: { title: 'Pi', art: 'pi' },
  agy: { title: 'Antigravity', art: 'antigravity' },
}

// The server serves its write token only inside the page (ADR 0017); every POST sends it back.
const TOKEN = document.querySelector<HTMLMetaElement>('meta[name="orca-board-token"]')?.content ?? ''
export const post = (url: string, body: unknown) =>
  fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Orca-Board-Token': TOKEN }, body: JSON.stringify(body) }).then(r => r.json())

export const ManifestContext = createContext<Manifest>({})

export function useManifest() {
  const [manifest, setManifest] = useState<Manifest>({})
  useEffect(() => {
    fetch('/avatars/manifest.json').then(r => (r.ok ? r.json() : {})).then(setManifest, () => {})
  }, [])
  return manifest
}

// The bands' 24 px Harness Avatar frames, cycled; a harness without this art draws Claude's, as avatarArt does.
export function Avatar({ harness: given, state, mood: givenMood, status }: { harness: string | null; state: string; mood: string | null; status: string }) {
  const manifest = useContext(ManifestContext)
  const harness = given ?? 'claude'
  const mood = givenMood ?? 'default'
  const own = HARNESSES[harness]?.art ?? harness
  const name = `${`${own}_${state}_${mood}_24` in manifest ? own : 'claude'}_${state}_${mood}_24`
  const frames = manifest[name]?.frames ?? 1
  const [frame, setFrame] = useState(0)
  useEffect(() => {
    if (frames < 2 || REDUCED_MOTION) return
    const id = setInterval(() => setFrame(f => (f + 1) % frames), FRAME_MS)
    return () => clearInterval(id)
  }, [frames])
  const label = `${HARNESSES[harness]?.title ?? harness}, ${status}`
  return (
    <span className="av">
      <img src={`avatars/${name}_${frame % frames}.svg`} alt={label} title={label} width={24} height={24} />
    </span>
  )
}

export const elapsed = (since: string | null) => {
  const ms = Date.now() - Date.parse(since ?? '')
  if (!Number.isFinite(ms) || ms < 0) return null
  const m = Math.floor(ms / 60000)
  return m < 60 ? `${m}m` : m < 1440 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${Math.floor(m / 1440)}d ${Math.floor((m % 1440) / 60)}h`
}

// The one tokens formatter: the chart, its axis and every usage title use it.
export const tokens = (n: number) => (n < 1000 ? `${Math.round(n)}` : n < 1e6 ? `${(n / 1000).toFixed(1)}k` : `${(n / 1e6).toFixed(1)}M`)
// A dash, never 0, where the harness has no parser or the log is missing.
export const money = (u: Usage | null) => (u ? `$${u.cost.toFixed(2)}` : '—')
export const usageTitle = (u: Usage | null) =>
  u ? `${tokens(u.input)} in · ${tokens(u.output)} out · ${tokens(u.cacheRead)} cache read · ${tokens(u.cacheWrite)} cache write` : 'No usage recorded'

// The cursor spotlight every card draws: the pointer's position, in the card's own pixels.
const spotlight = (e: PointerEvent<HTMLElement>) => {
  const r = e.currentTarget.getBoundingClientRect()
  e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`)
  e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`)
}

export const Card = ({ className, children }: { className: string; children: ReactNode }) => (
  <article className={`card ${className}`} onPointerMove={spotlight}>{children}</article>
)

// Radix Tabs with an indicator that slides to the active trigger. `dot` marks a tab with something to look at.
export function SlidingTabs({ tabs, value, onChange }: { tabs: { id: string; label: string; n?: number; dot?: string }[]; value: string; onChange: (v: string) => void }) {
  const list = useRef<HTMLDivElement>(null)
  const [ind, setInd] = useState({ left: 0, width: 0 })
  useLayoutEffect(() => {
    const el = list.current
    if (!el) return
    const place = () => {
      const a = el.querySelector<HTMLElement>('[data-state="active"]')
      if (a) setInd({ left: a.offsetLeft, width: a.offsetWidth })
    }
    place()
    const ro = new ResizeObserver(place)
    ro.observe(el)
    return () => ro.disconnect()
  }, [value, tabs.map(t => `${t.id}${t.n}${t.dot}`).join()])
  return (
    <Tabs.List className="tabs" ref={list}>
      {tabs.map(t => (
        <Tabs.Trigger key={t.id} value={t.id} onClick={() => onChange(t.id)}>
          {t.label}{t.n != null && <span className="n">{t.n}</span>}
          {t.dot && <span className="tab-dot" role="img" aria-label={t.dot} title={t.dot} />}
        </Tabs.Trigger>
      ))}
      <span className="ind" style={ind} aria-hidden />
    </Tabs.List>
  )
}
