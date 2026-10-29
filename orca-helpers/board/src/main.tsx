// The Board page: polls /api/board every 5 seconds and redraws in place, so no reload. The sidebar
// picks the page: the Status Page for every repo, or one repo's Repo Status Page.
import '@radix-ui/themes/styles.css'
import './board.css'
import { Theme } from '@radix-ui/themes'
import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ManifestContext, useManifest } from './common'
import { focusBudget, RepoStatusPage, type RepoTab } from './RepoStatusPage'
import { Sidebar } from './Sidebar'
import { needsAttention, StatusPage } from './StatusPage'
import { TopBar, type Theme as Appearance } from './TopBar'
import { repoKey, type Board } from './types'

const POLL_MS = 5000

// Each poll schedules the next from its `finally`, so a slow build never stacks requests.
function useBoard() {
  const [board, setBoard] = useState<Board | null>(null)
  const [down, setDown] = useState(false)
  const [updatedAt, setUpdatedAt] = useState<number | null>(null)
  useEffect(() => {
    let live = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const poll = () =>
      fetch('/api/board', { cache: 'no-store' })
        .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
        .then(b => live && (setBoard(b), setDown(false), setUpdatedAt(Date.now())))
        .catch(() => live && setDown(true))
        .finally(() => {
          if (live) timer = setTimeout(poll, POLL_MS)
        })
    poll()
    return () => ((live = false), clearTimeout(timer))
  }, [])
  return { board, down, updatedAt }
}

// The viewer's theme; storage can throw in a private window, so a failed read keeps the system's.
const SYSTEM: Appearance = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
function useTheme() {
  const [theme, setTheme] = useState<Appearance>(() => {
    try {
      const v = localStorage.getItem('orca-board-theme')
      return v === 'light' || v === 'dark' ? v : SYSTEM
    } catch {
      return SYSTEM
    }
  })
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('orca-board-theme', theme)
    } catch {}
  }, [theme])
  return [theme, setTheme] as const
}

function App() {
  const { board, down, updatedAt } = useBoard()
  const manifest = useManifest()
  const [theme, setTheme] = useTheme()
  const [current, setCurrent] = useState<string | null>(null)
  const [tab, setTab] = useState<RepoTab>('waves')
  const open = (key: string | null) => (setCurrent(key), setTab('waves'))
  const repo = board?.repos.find(r => repoKey(r) === current)
  const needs = board ? needsAttention(board) : []
  return (
    <ManifestContext.Provider value={manifest}>
      <Theme appearance={theme} accentColor="cyan" hasBackground={false}>
        <div className="app">
          <Sidebar board={board} current={repo ? current : null} needs={needs} onOpen={open} />
          <div className="body">
            <TopBar down={down} updatedAt={updatedAt} pollSeconds={POLL_MS / 1000} theme={theme} onTheme={setTheme} />
            <main>
              {!board ? (
                <p className="hint">Loading the Board…</p>
              ) : repo ? (
                <RepoStatusPage key={current} board={board} repo={repo} tab={tab} onTab={setTab} />
              ) : (
                <StatusPage board={board} onOpen={open} onBudget={r => (setCurrent(repoKey(r)), setTab('config'), focusBudget())} />
              )}
            </main>
          </div>
        </div>
      </Theme>
    </ManifestContext.Provider>
  )
}

createRoot(document.getElementById('root')!).render(<App />)
