import { describe, expect, it } from 'vitest'
import { limitLines, mergeComparison, mergeSimulation, ranges } from './series'
import type { Limit, SimulationResult } from '../types'

function point(t: number, soc: number) {
  return { t_min: t, soc_pct: soc } as unknown as SimulationResult['scenario'][number]
}

const result = {
  baseline: [point(0, 80), point(1, 79)],
  scenario: [point(0, 80), point(1, 70)],
  band: [
    { t_min: 0, soc_pct_lo: 80, soc_pct_hi: 80 },
    { t_min: 1, soc_pct_lo: 68, soc_pct_hi: 72 },
  ],
} as unknown as SimulationResult

describe('series', () => {
  it('merges baseline, prediction and band', () => {
    expect(mergeSimulation(result, 'soc_pct')).toEqual([
      { t_min: 0, baseline: 80, predicted: 80, band: [80, 80] },
      { t_min: 1, baseline: 79, predicted: 70, band: [68, 72] },
    ])
  })

  it('merges two scenarios for comparison', () => {
    const b = { ...result, scenario: [point(0, 80), point(1, 75)] } as SimulationResult
    expect(mergeComparison(result, b, 'soc_pct')[1]).toEqual({ t_min: 1, baseline: 79, a: 70, b: 75 })
  })

  it('finds contiguous ranges', () => {
    const rows = [0, 1, 2, 3, 4, 5].map((t) => ({ t, on: t === 1 || t === 2 || t === 5 }))
    expect(ranges(rows, (r) => r.t, (r) => r.on)).toEqual([
      [1, 2],
      [5, 5],
    ])
  })

  it('builds limit lines for a channel', () => {
    const limits: Limit[] = [
      { channel: 'soc_pct', label: 'SOC', unit: '%', warn_low: 40, crit_low: 25, warn_high: null, crit_high: null },
    ]
    expect(limitLines(limits, 'soc_pct').map((l) => [l.value, l.severity])).toEqual([
      [40, 'warning'],
      [25, 'critical'],
    ])
    expect(limitLines(limits, 'bus_temp_c')).toEqual([])
  })
})
