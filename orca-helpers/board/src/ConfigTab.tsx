// A repo's Config tab (Board design pick 10) and the form it shares with the Workstream config modal (pick 11).
// The form reads only what /api/board already sent; harness and model lists grow only when the user presses Refresh.
// `onUnsaved` reports the unsaved-change count for the tab's dot.
import { Switch } from '@radix-ui/themes'
import { useEffect, useState, type ReactNode } from 'react'
import { HARNESSES, post } from './common'
import type { Harness, Repo, Settings, Slot, SlotName, Workstream } from './types'
import { WorkstreamConfigModal } from './WorkstreamConfigModal'

/** The keys a Workstream may override: write_workstream_config.py KEYS. */
export const KEYS = ['harnesses', 'mainOrchestratorHarness', 'maxConcurrency', 'targetBranch', 'review', 'planGate', 'evidenceCommand', 'budgetUsd', 'taskTime'] as const
export type Key = (typeof KEYS)[number]
export type Values = Required<Pick<Settings, Key>>

const TASK_TIMES = [['low', 'Low, under 5 minutes'], ['medium', 'Medium, under 10'], ['high', 'High, under 15'], ['xhigh', 'Extra High, under 30'], ['ultra', 'Ultra High, 30 or more']]
const EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max']
const SLOTS: [SlotName, string][] = [
  ['mainOrchestrator', 'Runs the orchestrator session'],
  ['orchestrationWorker', 'Runs each Work Item'],
  ['subagent', 'Subagents a worker spawns'],
  ['subagentSimple', 'Subagents for simple tasks'],
]
// shortcut: a name match, not real prices; read prices.json through the payload if the glyphs mislead.
const cost = (m: string) => (/haiku|luna|mini|flash/.test(m) ? '$' : /large|sol|ultra|opus/.test(m) ? '$$$' : '$$')

/** Each value with the defaults write_settings.py gives a missing optional key. */
export const normalise = (s: Partial<Settings>): Values => ({
  harnesses: s.harnesses ?? [],
  mainOrchestratorHarness: s.mainOrchestratorHarness ?? null,
  maxConcurrency: s.maxConcurrency ?? null,
  targetBranch: s.targetBranch ?? '',
  review: s.review ?? true,
  planGate: s.planGate ?? false,
  evidenceCommand: s.evidenceCommand ?? null,
  budgetUsd: s.budgetUsd ?? null,
  taskTime: s.taskTime ?? 'medium',
})

// Key order differs between files the scripts wrote and objects the form built, so compare with sorted keys.
const stable = (v: unknown): string =>
  v && typeof v === 'object' && !Array.isArray(v)
    ? `{${Object.keys(v).sort().map(k => `${JSON.stringify(k)}:${stable((v as Record<string, unknown>)[k])}`).join(',')}}`
    : Array.isArray(v) ? `[${v.map(stable).join(',')}]` : JSON.stringify(v ?? null)
export const same = (a: unknown, b: unknown) => stable(a) === stable(b)

/** The keys a Workstream's `_config.json` sets apart from its repo's Prompt Settings. */
export const overridden = (repo: Repo, ws: Workstream): Key[] =>
  KEYS.filter(k => k in ws.config && (!repo.settings || !same(ws.config[k], normalise(repo.settings)[k])))

const slotModel = (s: Slot) => (typeof s === 'string' ? s : s?.model ?? '')
const slotEffort = (s: Slot) => (s && typeof s === 'object' ? s.effort ?? '' : '')
const names = (v: Values) => v.harnesses.map(h => h.name)
const blank = (name: string): Harness => ({ name, cli: null, tier: 'standard', models: { mainOrchestrator: null, orchestrationWorker: null, subagent: null, subagentSimple: null } })

// The form's sections; the Agent Harnesses and Model Slots sections both write `harnesses`.
type Section = 'harnesses' | 'slots' | Exclude<Key, 'harnesses'>
const changed = (v: Values, b: Values, s: Section) =>
  s === 'harnesses' ? !same(names(v), names(b)) : s === 'slots' ? v.harnesses.some(h => { const o = b.harnesses.find(x => x.name === h.name); return o && !same(h, o) }) : !same(v[s], b[s])
export const SECTIONS: Section[] = ['harnesses', 'mainOrchestratorHarness', 'slots', 'maxConcurrency', 'targetBranch', 'review', 'planGate', 'evidenceCommand', 'budgetUsd', 'taskTime']
export const countChanges = (v: Values, b: Values) => SECTIONS.filter(s => changed(v, b, s)).length

/** Every model the loaded data names for each harness: the repo's Prompt Settings and each Workstream's config. */
function loadedModels(repo: Repo) {
  const found: Record<string, Set<string>> = {}
  for (const s of [repo.settings, ...repo.workstreams.map(ws => ws.config)])
    for (const h of s?.harnesses ?? []) for (const slot of Object.values(h.models ?? {})) if (slotModel(slot)) (found[h.name] ??= new Set()).add(slotModel(slot))
  return found
}

type Refreshed = { harnesses: { name: string; installed: boolean }[]; models: Record<string, { providers?: Record<string, { model: string }[]> }> }

export const Fails = ({ lines }: { lines: string[] }) =>
  lines.length > 0 && <ul className="fails" role="alert">{lines.map(l => <li key={l}>{l}</li>)}</ul>

/** Override a section, for the modal: off shows the repo default, greyed and locked. */
export type Overrides = { on: Record<Key, boolean>; locked: boolean; onToggle: (k: Key) => void }

export function ConfigForm({ repo, value, base, onChange, overrides, extra }: {
  repo: Repo; value: Values; base: Values; onChange: (v: Values) => void; overrides?: Overrides; extra?: ReactNode
}) {
  const [parked, setParked] = useState<Record<string, Harness>>({})
  const [picked, setPicked] = useState<string | null>(null)
  const [refreshed, setRefreshed] = useState<Refreshed | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<string[]>([])
  const on = names(value)
  const hsel = picked && on.includes(picked) ? picked : value.mainOrchestratorHarness && on.includes(value.mainOrchestratorHarness) ? value.mainOrchestratorHarness : on[0] ?? null
  const known = [...new Set([...Object.keys(HARNESSES), ...on, ...(refreshed?.harnesses.map(h => h.name) ?? [])])]
  const models: Record<string, Set<string>> = loadedModels(repo)
  for (const [h, m] of Object.entries(refreshed?.models ?? {})) for (const list of Object.values(m.providers ?? {})) for (const x of list) (models[h] ??= new Set()).add(x.model)
  const set = <K extends Key>(k: K, v: Values[K]) => onChange({ ...value, [k]: v })
  const setHarness = (h: Harness) => set('harnesses', value.harnesses.map(x => (x.name === h.name ? h : x)))

  const toggle = (name: string) => {
    if (on.includes(name)) {
      const rest = value.harnesses.filter(h => h.name !== name)
      setParked({ ...parked, [name]: value.harnesses.find(h => h.name === name)! })
      const main = value.mainOrchestratorHarness === name ? rest[0]?.name ?? null : value.mainOrchestratorHarness
      onChange({ ...value, harnesses: rest, mainOrchestratorHarness: main })
    } else {
      const back = parked[name] ?? base.harnesses.find(h => h.name === name) ?? blank(name)
      // Keep the chips' order, so turning a harness off and on again is no change.
      const order = (h: Harness) => known.indexOf(h.name)
      onChange({ ...value, harnesses: [...value.harnesses, back].sort((a, b) => order(a) - order(b)), mainOrchestratorHarness: value.mainOrchestratorHarness ?? name })
    }
  }
  const refresh = () => {
    setBusy(true)
    post('/api/refresh', {})
      .then(r => {
        if (!r.ok) return setNote(r.fail ?? ['FAIL: Refresh failed'])
        setRefreshed(r)
        const n = Object.values(r.models as Refreshed['models']).reduce((t, m) => t + Object.values(m.providers ?? {}).flat().length, 0)
        setNote([`Updated ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}. ${r.harnesses.filter((h: { installed: boolean }) => h.installed).length} harnesses installed, ${n} models listed.`])
      }, () => setNote(['FAIL: the Board server did not answer']))
      .finally(() => setBusy(false))
  }

  const fld = (s: Section, title: string, hint: string, body: ReactNode) => {
    const k: Key = s === 'slots' ? 'harnesses' : s
    const off = overrides ? !overrides.on[k] : false
    return (
      <div className={`fld${off ? ' inherit' : ''}`}>
        <div className="fld-h">
          <div>
            <h4>{title}{changed(value, base, s) && <i className="ddot" role="img" aria-label="Changed" title="Changed" />}</h4>
            <p className="hint">{hint}</p>
          </div>
          {overrides && (
            <label className="ov">
              <Switch size="1" checked={!off} disabled={overrides.locked} onCheckedChange={() => overrides.onToggle(k)} aria-label={`Override ${title}`} />
              Override
            </label>
          )}
        </div>
        <fieldset disabled={off}>{body}</fieldset>
        {off && <p className="inh">Follows the {repo.name} default</p>}
      </div>
    )
  }

  const slotRow = (h: Harness, s: SlotName, hint: string) => {
    const slot = h.models[s]
    const model = slotModel(slot)
    const list = [...new Set([...(models[h.name] ?? []), ...(model ? [model] : [])])].sort()
    const write = (m: string, e: string) => setHarness({ ...h, models: { ...h.models, [s]: !m ? null : e ? { model: m, effort: e } : m } })
    return (
      <div className="slotrow" key={s}>
        <div><span className="sn mono">{s}</span><span className="hint">{hint}</span></div>
        <div className="mcell">
          <select aria-label={`${s} model`} value={model} onChange={e => write(e.target.value, slotEffort(slot))}>
            <option value="">None</option>
            {list.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          {model && <span className="cg" title="Relative cost tier">{cost(model)}</span>}
        </div>
        <select aria-label={`${s} effort`} value={slotEffort(slot)} disabled={!model} onChange={e => write(model, e.target.value)}>
          <option value="">no effort</option>
          {EFFORTS.map(x => <option key={x} value={x}>{x}</option>)}
        </select>
      </div>
    )
  }
  const h = value.harnesses.find(x => x.name === hsel)
  const sameForAll = (h: Harness) => {
    const w = h.models.orchestrationWorker
    setHarness({ ...h, models: { ...h.models, subagent: w, subagentSimple: h.models.subagentSimple === null ? null : w } })
  }

  return (
    <div className="cfg-grid">
      <div className="cfg-col">
        {fld('harnesses', 'Agent Harnesses', 'Which CLIs a Workstream may use.', (
          <div className="hchips" role="group" aria-label="Agent Harnesses">
            {known.map(n => {
              const missing = refreshed && !refreshed.harnesses.find(x => x.name === n)?.installed
              return (
                <button key={n} type="button" className="hchip" role="checkbox" aria-checked={on.includes(n)} onClick={() => toggle(n)} title={missing ? 'Not installed' : undefined}>
                  <span className="cbx"><svg className="tick" viewBox="0 0 12 12" aria-hidden><path d="M2.5 6.5l2.3 2.3L9.5 3.5" /></svg></span>
                  <img src={`avatars/${HARNESSES[n]?.art ?? 'claude'}_main_0.svg`} alt="" width={20} height={20} />
                  {HARNESSES[n]?.title ?? n}
                </button>
              )
            })}
          </div>
        ))}
        {fld('mainOrchestratorHarness', 'Main Orchestrator harness', 'The harness that runs the orchestrator session.', (
          <div className="segctl" role="radiogroup" aria-label="Main Orchestrator harness">
            {known.map(n => (
              <button key={n} type="button" role="radio" aria-checked={value.mainOrchestratorHarness === n} disabled={!on.includes(n)}
                title={on.includes(n) ? undefined : 'Not in the allowed Agent Harnesses'} onClick={() => (set('mainOrchestratorHarness', n), setPicked(n))}>
                {HARNESSES[n]?.title ?? n}
              </button>
            ))}
          </div>
        ))}
        {fld('slots', 'Model Slots', 'A model and effort for each job a harness does.', (
          <div className="slotbox">
            <div className="htabs" role="tablist" aria-label="Harness">
              {on.map(n => <button key={n} type="button" role="tab" aria-selected={hsel === n} onClick={() => setPicked(n)}>{HARNESSES[n]?.title ?? n}</button>)}
            </div>
            {!h ? <p className="hint" style={{ padding: 12 }}>Turn on at least one Agent Harness.</p> : (
              <>
                <div className="slothead">
                  <span className="hint">Tier for {HARNESSES[h.name]?.title ?? h.name}</span>
                  <div className="sh-r">
                    <button type="button" className="chip" onClick={() => sameForAll(h)} title="Copy the orchestrationWorker model and effort to the subagent slots">Same for all slots</button>
                    <select aria-label="Tier" value={h.tier} onChange={e => setHarness({ ...h, tier: e.target.value as Harness['tier'] })}>
                      <option value="light">light</option>
                      <option value="standard">standard</option>
                    </select>
                  </div>
                </div>
                {SLOTS.filter(([s]) => s !== 'mainOrchestrator' || value.mainOrchestratorHarness === h.name).map(([s, d]) => slotRow(h, s, d))}
              </>
            )}
          </div>
        ))}
        <div className="rf">
          <button type="button" className="chip" disabled={busy} onClick={refresh}>{busy ? 'Refreshing…' : '↻ Refresh models & harnesses'}</button>
          <span className="hint" role="status">{note.length ? note.filter(l => !l.startsWith('FAIL:')).join(' ') : 'Model and harness lists load once. They are not polled.'}</span>
          <Fails lines={note.filter(l => l.startsWith('FAIL:'))} />
        </div>
      </div>
      <div className="cfg-col">
        {extra}
        {fld('taskTime', 'Task Time', 'How long each Work Item is meant to take. Every generated prompt carries it.', (
          <select aria-label="Task Time" value={value.taskTime} onChange={e => set('taskTime', e.target.value)}>
            {TASK_TIMES.map(([t, label]) => <option key={t} value={t}>{label}</option>)}
          </select>
        ))}
        {fld('maxConcurrency', 'Max concurrency', 'Orchestrator, subagents and nested subagents combined.', (
          <input type="number" aria-label="Max concurrency" min={1} max={64} value={value.maxConcurrency ?? ''}
            onChange={e => set('maxConcurrency', e.target.value === '' ? null : Number(e.target.value))} />
        ))}
        {fld('targetBranch', 'Target branch', 'Where each Work Item result lands.', (
          <input type="text" className="mono" aria-label="Target branch" value={value.targetBranch} onChange={e => set('targetBranch', e.target.value)} />
        ))}
        {fld('review', 'Work Item review', 'Another harness reviews each diff before it ships.', (
          <label className="swrow">Review each Work Item<Switch checked={value.review} onCheckedChange={v => set('review', v)} /></label>
        ))}
        {fld('planGate', 'Plan gate', 'A second agent reads the plan before Wave 1.', (
          <label className="swrow">Run a plan gate<Switch checked={value.planGate} onCheckedChange={v => set('planGate', v)} /></label>
        ))}
        {fld('evidenceCommand', 'Evidence command', 'Run to prove a Work Item works. Leave empty for none.', (
          <input type="text" className="mono" aria-label="Evidence command" placeholder="npm test" value={value.evidenceCommand ?? ''}
            onChange={e => set('evidenceCommand', e.target.value === '' ? null : e.target.value)} />
        ))}
        {fld('budgetUsd', 'Budget', 'Leave empty for no budget. The Board then shows spend alone.', (
          <div className="pre"><span className="muted">$</span>
            {/* The Spend panel's "Set a budget" link focuses #budgetUsd; the modal's copy of the form leaves it to the tab. */}
            <input id={overrides ? undefined : 'budgetUsd'} type="number" aria-label="Budget in USD" min={1} step={1} placeholder="No budget" value={value.budgetUsd ?? ''}
              onChange={e => set('budgetUsd', e.target.value === '' ? null : Number(e.target.value))} />
          </div>
        ))}
      </div>
    </div>
  )
}

export function ConfigTab({ repo, onUnsaved }: { repo: Repo; onUnsaved?: (n: number) => void }) {
  const loaded = repo.settings && normalise(repo.settings)
  const [base, setBase] = useState(loaded)
  const [value, setValue] = useState(loaded)
  const [name, setName] = useState(repo.name)
  const [baseName, setBaseName] = useState(repo.name)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<string[]>([])
  const [open, setOpen] = useState<Workstream | null>(null)
  const n = (value && base ? countChanges(value, base) : 0) + (name.trim() !== baseName ? 1 : 0)
  useEffect(() => onUnsaved?.(n), [n])
  // A poll that brings new settings or a new Repo Name replaces the form only while nothing is unsaved.
  useEffect(() => {
    if (n) return
    setBase(loaded), setValue(loaded), setName(repo.name), setBaseName(repo.name)
  }, [stable(repo.settings), repo.name])

  const discard = () => (setValue(base), setName(baseName), setStatus([]))
  const save = async () => {
    setBusy(true)
    const fails: string[] = []
    try {
      if (value && base && countChanges(value, base)) {
        const r = await post('/api/settings', { repo: repo.path, settings: { ...repo.settings, ...value } })
        r.ok ? setBase(value) : fails.push(...(r.fail ?? ['FAIL: saving Prompt Settings failed']))
      }
      if (name.trim() !== baseName) {
        const r = await post('/api/repo-name', { repo: repo.path, name: name.trim() })
        r.ok ? setBaseName(name.trim()) : fails.push(...(r.fail ?? ['FAIL: saving the Repo Name failed']))
      }
    } catch {
      fails.push('FAIL: the Board server did not answer')
    }
    setBusy(false)
    setStatus(fails.length ? fails : ['Saved. New Workstreams start from these defaults.'])
  }

  if (!repo.path) return <p className="hint">{repo.slug} has no local checkout, so it has no Prompt Settings to edit.</p>
  return (
    <div className="sec cfg">
      {!value && <p className="hint">No valid Prompt Settings in {repo.path}/.orca/prompts/prompt-settings.json. Run /orca-prompt-settings in a session to create them.</p>}
      {value && base ? (
        <ConfigForm repo={repo} value={value} base={base} onChange={v => (setValue(v), setStatus([]))} extra={<RepoName name={name} changed={name.trim() !== baseName} onChange={v => (setName(v), setStatus([]))} />} />
      ) : (
        <RepoName name={name} changed={name.trim() !== baseName} onChange={v => (setName(v), setStatus([]))} />
      )}
      <div className="cfg-foot sticky">
        <span className={`dirtytxt${n ? ' on' : ''}`} role="status">{n ? `${n} unsaved change${n === 1 ? '' : 's'}` : 'No unsaved changes'}</span>
        <p className="hint">Saving writes .orca/prompts/prompt-settings.json. Running Workstreams keep their own config.</p>
        <button type="button" className="chip" disabled={!n || busy} onClick={discard}>Discard</button>
        <button type="button" className="chip primary" disabled={!n || busy} onClick={save}>{busy ? 'Saving…' : 'Save defaults'}</button>
        {status.length > 0 && !status[0].startsWith('FAIL:') && <span className="saved" role="status">{status[0]}</span>}
        <Fails lines={status.filter(l => l.startsWith('FAIL:'))} />
      </div>
      <div className="panel-sub">
        <h4>Workstream overrides</h4>
        {repo.workstreams.map(ws => {
          const keys = overridden(repo, ws)
          return (
            <div key={ws.name} className="cfg-row">
              <span><b>{ws.name}</b> <span className="hint">{ws.active ? 'Running: its config is locked' : keys.length ? `${keys.length} override${keys.length === 1 ? '' : 's'}` : 'Follows the repo defaults'}</span></span>
              <button type="button" className="chip" disabled={ws.active} onClick={() => setOpen(ws)}>⚙ Config</button>
            </div>
          )
        })}
      </div>
      {open && <WorkstreamConfigModal repo={repo} workstream={open} onClose={() => setOpen(null)} />}
    </div>
  )
}

const RepoName = ({ name, changed, onChange }: { name: string; changed: boolean; onChange: (v: string) => void }) => (
  <div className="fld">
    <div className="fld-h"><div><h4>Repo Name{changed && <i className="ddot" role="img" aria-label="Changed" title="Changed" />}</h4><p className="hint">What the Board calls this repo.</p></div></div>
    <input type="text" aria-label="Repo Name" maxLength={100} value={name} onChange={e => onChange(e.target.value)} />
  </div>
)
