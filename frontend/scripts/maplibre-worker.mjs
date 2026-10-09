// MapLibre GL 6 loads its web worker from a file next to its own module URL, which breaks once Vite bundles the
// module. Copy the worker (and the shared chunk it imports) into public/maplibre so the app can point MapLibre at a
// stable URL with setWorkerUrl(). Runs before `dev` and `build`.
import { copyFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const src = join(here, '..', 'node_modules', 'maplibre-gl', 'dist')
const dest = join(here, '..', 'public', 'maplibre')
mkdirSync(dest, { recursive: true })
for (const name of ['maplibre-gl-worker.mjs', 'maplibre-gl-shared.mjs']) copyFileSync(join(src, name), join(dest, name))
console.log('copied MapLibre worker to public/maplibre')
