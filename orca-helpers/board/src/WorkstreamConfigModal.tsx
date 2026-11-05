// One Workstream's overrides in a modal (Board design pick 11): every section of the Config tab's form with an
// Override switch, Save and Cancel in the footer. The body scrolls inside the viewport, so Save stays reachable.
import { Dialog } from '@radix-ui/themes'
import { useState } from 'react'
import { post } from './common'
import { ConfigForm, Fails, KEYS, normalise, overridden, same, type Key, type Values } from './ConfigTab'
import type { Repo, Workstream } from './types'

export function WorkstreamConfigModal({ repo, workstream: ws, onClose }: { repo: Repo; workstream: Workstream; onClose: () => void }) {
  const defaults = repo.settings && normalise(repo.settings)
  // With no Prompt Settings there is no default to follow, so every section is the Workstream's own.
  const [init] = useState(() => {
    const keys = overridden(repo, ws)
    const on = Object.fromEntries(KEYS.map(k => [k, !defaults || keys.includes(k)])) as Record<Key, boolean>
    const own = normalise(ws.config)
    const value = Object.fromEntries(KEYS.map(k => [k, on[k] ? own[k] : defaults![k]])) as Values
    return { on, value }
  })
  const [on, setOn] = useState(init.on)
  const [value, setValue] = useState(init.value)
  const [busy, setBusy] = useState(false)
  const [fails, setFails] = useState<string[]>([])
  const dirty = !same(on, init.on) || !same(value, init.value)

  // Off follows the repo default: the section shows it, and Save clears the key.
  const toggle = (k: Key) => {
    setOn({ ...on, [k]: !on[k] })
    if (on[k] && defaults) setValue({ ...value, [k]: defaults[k] })
  }
  const save = () => {
    setBusy(true)
    // Only switched-on sections are overrides; a switched-off one is cleared so it follows the repo default.
    const overrides = Object.fromEntries(KEYS.filter(k => on[k]).map(k => [k, value[k]]))
    post('/api/workstream-config', { repo: repo.path, workstream: ws.name, overrides, clear: KEYS.filter(k => !on[k]) })
      .then(r => (r.ok ? onClose() : setFails(r.fail ?? ['FAIL: saving the overrides failed'])), () => setFails(['FAIL: the Board server did not answer']))
      .finally(() => setBusy(false))
  }

  return (
    <Dialog.Root open onOpenChange={o => !o && onClose()}>
      <Dialog.Content className="modal cfg-modal" maxWidth="980px">
        <div className="modal-h">
          <Dialog.Title size="4" mb="1">Config · {ws.name}</Dialog.Title>
          <Dialog.Description size="2" color="gray">
            {repo.name} · {ws.active ? 'Running, so its config is locked.' : `Turn on Override for what this Workstream should change. The rest follows the ${repo.name} defaults.`}
          </Dialog.Description>
        </div>
        <div className="modal-b">
          <ConfigForm repo={repo} value={value} base={init.value} onChange={setValue} overrides={{ on, locked: !defaults || ws.active, onToggle: toggle }} />
        </div>
        <div className="modal-f">
          <p className="hint">Saving writes this Workstream's _config.json. It applies the next time this Workstream runs.</p>
          <Fails lines={fails} />
          <Dialog.Close><button type="button" className="chip">Cancel</button></Dialog.Close>
          <button type="button" className="chip primary" disabled={busy || ws.active || !repo.path || !dirty} onClick={save}>{busy ? 'Saving…' : 'Save'}</button>
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
