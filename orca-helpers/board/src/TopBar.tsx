// The top bar (Board design pick 2): the poll state on the left, the Light/Dark switch on the right.
import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

export function TopBar({ down, updatedAt, pollSeconds, theme, onTheme }: { down: boolean; updatedAt: number | null; pollSeconds: number; theme: Theme; onTheme: (t: Theme) => void }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])
  const ago = updatedAt == null ? null : Math.max(0, Math.round((now - updatedAt) / 1000))
  return (
    <header className="bar">
      <span className={`live${down ? ' down' : ''}`} role="status">
        <i className="pulse" key={updatedAt ?? 0} aria-hidden />
        <b>{down ? 'Board server not answering: run /orca-board' : `Polling ${pollSeconds}s`}</b>
        {ago != null && <span className="muted">updated {ago}s ago</span>}
      </span>
      <span className="spacer" />
      <div className="seg" role="group" aria-label="Theme">
        {(['light', 'dark'] as const).map(t => <button key={t} type="button" aria-pressed={t === theme} onClick={() => onTheme(t)}>{t === 'light' ? 'Light' : 'Dark'}</button>)}
      </div>
    </header>
  )
}
