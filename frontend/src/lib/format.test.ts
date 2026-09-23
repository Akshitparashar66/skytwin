import { describe, expect, it } from 'vitest'
import { duration, missionTime, relTick, signed, withUnit } from './format'

describe('format', () => {
  it('formats mission time', () => {
    expect(missionTime(0)).toBe('T+00:00')
    expect(missionTime(95.9)).toBe('T+01:35')
    expect(missionTime(-3)).toBe('T+00:00')
  })

  it('formats durations', () => {
    expect(duration(34)).toBe('34 min')
    expect(duration(60)).toBe('1 h')
    expect(duration(252)).toBe('4 h 12 min')
  })

  it('formats relative axis ticks', () => {
    expect(relTick(0)).toBe('0')
    expect(relTick(45)).toBe('45m')
    expect(relTick(120)).toBe('2h')
    expect(relTick(90)).toBe('1h30')
  })

  it('formats values with units', () => {
    expect(withUnit(42.345, '%')).toBe('42.3%')
    expect(withUnit(3.4, 'A', 2)).toBe('3.40 A')
    expect(withUnit(null, 'W')).toBe('—')
    expect(signed(2)).toBe('+2.0')
    expect(signed(-1.25, 2)).toBe('-1.25')
  })
})
