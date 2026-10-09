import type { Band } from './api'

export const BAND_COLOR: Record<Band, string> = {
  clear: '#9ad0a0',
  light: '#f3d98b',
  moderate: '#f3a35a',
  heavy: '#e05a3a',
  severe: '#8b1e4b',
}

export const BAND_LABEL: Record<Band, string> = {
  clear: 'Clear',
  light: 'Light',
  moderate: 'Moderate',
  heavy: 'Heavy',
  severe: 'Severe',
}

const IST = 'Asia/Kolkata'

export function istTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-IN', { hour: 'numeric', hour12: true, timeZone: IST }).replace(' ', ' ').toLowerCase()
}

export function istDay(iso: string): string {
  return new Date(iso).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', timeZone: IST })
}

export function istFull(iso: string): string {
  return `${istDay(iso)}, ${istTime(iso)}`
}

export function relativeDay(iso: string, nowIso: string): string {
  const d = new Date(iso)
  const n = new Date(nowIso)
  const dayOf = (x: Date) => new Date(x.toLocaleDateString('en-US', { timeZone: IST })).getTime()
  const diff = Math.round((dayOf(d) - dayOf(n)) / 86_400_000)
  if (diff === 0) return 'Today'
  if (diff === 1) return 'Tomorrow'
  if (diff === -1) return 'Yesterday'
  return istDay(iso)
}

export function formatCount(n: number): string {
  return n.toLocaleString('en-IN')
}
