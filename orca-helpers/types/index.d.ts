// Whether the Wave Band and the Prompt Band show their top bar alone.
export type Collapsed = boolean

// The files this session claimed as the Owning Session (hooks/owner.ts):
// `prompt` the _prompt-band.json, `wave` the Workstream's _status.json.
export type Owners = { prompt?: string; wave?: string }

// The toast states last seen for `workstream` (hooks/band.tsx), so a reload repeats no toast.
export type Toasted = { workstream: string; keys: string[] }

// Whether this session showed the pictures-off toast (hooks/images.ts).
export type ImagesToasted = boolean

declare module 'claude-code' {
  interface PluginState {
    'orca-helpers': { collapsed: Collapsed; owners: Owners; toasted: Toasted; imagesToasted: ImagesToasted }
  }
}
