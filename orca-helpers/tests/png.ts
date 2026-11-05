// Shared PNG stubs for the band tests. No `.test.` in the name, so the runner does not collect it.
// The PNG signature and a 1x1 IHDR chunk: what the engine checks of an Image's png.
export const PNG_HEAD = atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ')

// A PNG reads as a 1x1 PNG head and its own path, so a test sees which frame it drew.
export const pngRead = (path: string) => ({ value: { base64: btoa(PNG_HEAD + path) } }) as never

// The path a drawn Image reads from, with the PNG head stripped.
export const file = async (ui: any, key: string) => atob(((await ui.find({ type: 'Image', key }))!.props.source as { png: string }).png).slice(PNG_HEAD.length)

// A `.cells` file reads as blank cells at the size its name carries, as art/icons/cells.py writes it.
export const cellsRead = (path: string) => {
  const [, columns, rows] = path.match(/\.(\d+)x(\d+)\.cells$/)!.map(Number)
  const words = Array.from({ length: columns! * rows! }, () => [0x20, 0x01000000, 0x01000000]).flat()
  return { value: (new Uint8Array(Uint32Array.from(words).buffer) as Uint8Array & { toBase64(): string }).toBase64() } as never
}
