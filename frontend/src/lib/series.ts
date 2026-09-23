import type { Limit, SimulationResult } from '../types'

export type Row = Record<string, number | [number, number] | null>

/** Merge baseline, predicted and uncertainty band into chart rows keyed by t_min. */
export function mergeSimulation(result: SimulationResult, channel: string): Row[] {
  return result.scenario.map((point, i) => {
    const base = result.baseline[i]
    const band = result.band[i]
    const lo = band?.[`${channel}_lo`]
    const hi = band?.[`${channel}_hi`]
    return {
      t_min: point.t_min,
      baseline: base ? (base[channel as keyof typeof base] as number) : null,
      predicted: point[channel as keyof typeof point] as number,
      band: lo !== undefined && hi !== undefined ? [lo, hi] : null,
    }
  })
}

/** Merge two scenario runs (same snapshot) for side-by-side comparison. */
export function mergeComparison(a: SimulationResult, b: SimulationResult, channel: string): Row[] {
  return a.scenario.map((point, i) => ({
    t_min: point.t_min,
    baseline: a.baseline[i][channel as keyof (typeof a.baseline)[number]] as number,
    a: point[channel as keyof typeof point] as number,
    b: (b.scenario[i]?.[channel as keyof (typeof b.scenario)[number]] as number) ?? null,
  }))
}

/** Contiguous [start, end] ranges (in x units) where predicate holds. */
export function ranges<T>(rows: T[], x: (r: T) => number, predicate: (r: T) => boolean): [number, number][] {
  const out: [number, number][] = []
  let start: number | null = null
  let prev: number | null = null
  for (const r of rows) {
    if (predicate(r)) {
      if (start === null) start = x(r)
      prev = x(r)
    } else if (start !== null) {
      out.push([start, prev ?? start])
      start = null
    }
  }
  if (start !== null) out.push([start, prev ?? start])
  return out
}

export interface LimitLine {
  value: number
  label: string
  severity: 'warning' | 'critical'
}

export function limitLines(limits: Limit[] | undefined, channel: string): LimitLine[] {
  const limit = limits?.find((l) => l.channel === channel)
  if (!limit) return []
  const lines: LimitLine[] = []
  if (limit.warn_low !== null) lines.push({ value: limit.warn_low, label: 'warn', severity: 'warning' })
  if (limit.crit_low !== null) lines.push({ value: limit.crit_low, label: 'crit', severity: 'critical' })
  if (limit.warn_high !== null) lines.push({ value: limit.warn_high, label: 'warn', severity: 'warning' })
  if (limit.crit_high !== null) lines.push({ value: limit.crit_high, label: 'crit', severity: 'critical' })
  return lines
}
