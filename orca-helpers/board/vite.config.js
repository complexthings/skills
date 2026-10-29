// The Board bundle (ADR 0013). `pnpm build` writes dist/, which is committed so
// users need no Node, and dist/source-hash.txt, which test_board.py compares
// against the source to catch a bundle older than its source.
import { createHash } from 'node:crypto'
import { readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const ROOT = import.meta.dirname
const walk = dir => readdirSync(dir, { withFileTypes: true }).flatMap(e => (e.isDirectory() ? walk(join(dir, e.name)) : [join(dir, e.name)]))

// The same files, order and framing as source_hash() in test_board.py.
export function sourceHash() {
  const files = ['index.html', 'package.json', 'pnpm-lock.yaml', 'tsconfig.json', 'vite.config.js', ...walk(join(ROOT, 'src')).map(f => relative(ROOT, f).split('\\').join('/'))].sort()
  const hash = createHash('sha256')
  for (const f of files) hash.update(`${f}\0`).update(readFileSync(join(ROOT, f))).update('\0')
  return hash.digest('hex')
}

export default defineConfig({
  base: './',
  plugins: [react(), { name: 'source-hash', writeBundle: () => writeFileSync(join(ROOT, 'dist', 'source-hash.txt'), `${sourceHash()}\n`) }],
})
